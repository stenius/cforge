import asyncio
import json
import logging
import os
import random
import string
import threading
from datetime import datetime
from pathlib import Path

import kopf
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from kubernetes import client, config

from filters import datetimeformat

logging.basicConfig(level=logging.INFO)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
templates.env.filters["datetimeformat"] = datetimeformat
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "./artifacts")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/artifacts", StaticFiles(directory=ARTIFACT_DIR), name="artifacts")


# Load Kubernetes config or get it from the cluster
try:
    config.load_kube_config()
except config.config_exception.ConfigException:
    config.load_incluster_config()

k8s_client = client.ApiClient()
batch_v1 = client.BatchV1Api(k8s_client)

DEFAULT_SCHEDULE = "* * 31 2 *"


# looking up the job_template from the cronjob so I can call this from the web-ui to rebuild a project manually
def create_job_from_cronjob(project_name):
    """start a job from the cronjob template"""
    job_name = f"%s-%s" % (
        project_name,
        "".join(random.choices(string.ascii_lowercase + string.digits, k=8)),
    )
    # Get the CronJob
    cronjob = batch_v1.read_namespaced_cron_job(name=project_name, namespace="cforge")

    # Create Job from CronJob's template
    job_template = cronjob.spec.job_template
    job_template.metadata = client.V1ObjectMeta(name=job_name)

    # Create the job
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=job_template.metadata,
        spec=job_template.spec,
    )

    # Create the job in the specified namespace
    batch_v1.create_namespaced_job(namespace="cforge", body=job)
    logging.info(f"Job {job_name} created successfully from CronJob {project_name}")


def create_build_cronjob(project_name, repo_url, schedule):
    """create a kubernetes cronjob that attaches the artifact volume"""
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=project_name),
    )

    cronjob = client.V1CronJob(
        api_version="batch/v1",
        kind="CronJob",
        metadata=client.V1ObjectMeta(name=project_name, namespace="cforge"),
        spec=client.V1CronJobSpec(
            schedule=schedule if schedule else DEFAULT_SCHEDULE,
            job_template=client.V1JobTemplateSpec(
                spec=client.V1JobSpec(
                    ttl_seconds_after_finished=100,  # clean up the old jobs after 100 seconds
                    template=client.V1PodTemplateSpec(
                        spec=client.V1PodSpec(
                            containers=[
                                client.V1Container(
                                    name=project_name,
                                    image="ghcr.io/stenius/cforge/builder:latest",
                                    args=[project_name, repo_url],
                                    volume_mounts=[
                                        client.V1VolumeMount(
                                            name="artifacts", mount_path="/mnt/data"
                                        )
                                    ],
                                    env=[
                                        client.V1EnvVar(
                                            name="ARTIFACT_DIR", value="/mnt/data"
                                        )
                                    ],
                                )
                            ],
                            volumes=[
                                client.V1Volume(
                                    name="artifacts",
                                    persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                        claim_name="artifacts"
                                    ),
                                )
                            ],
                            restart_policy="Never",
                        )
                    ),
                ),
            ),
            suspend=not bool(schedule),  # disable cron if project isn't scheduled
        ),
    )

    existing_cronjobs = batch_v1.list_namespaced_cron_job(namespace="cforge")
    cronjob_names = [cj.metadata.name for cj in existing_cronjobs.items]
    if project_name in cronjob_names:
        batch_v1.replace_namespaced_cron_job(
            name=project_name, namespace="cforge", body=cronjob
        )
        logging.info(f"CronJob {project_name} updated successfully")
    else:
        batch_v1.create_namespaced_cron_job(namespace="cforge", body=cronjob)
        logging.info(f"CronJob {project_name} created successfully")

    # run the job whenever it is created or changed
    create_job_from_cronjob(project_name)


def delete_build_cronjob(project_name):
    batch_v1.delete_namespaced_cron_job(
        name=project_name,
        namespace="cforge",
        body=client.V1DeleteOptions(propagation_policy="Foreground"),
    )


@kopf.on.create("cforge.steni.us", "v1", "cforge")
def on_create(body, **kwargs):
    spec = body.get("spec", {})
    projects = spec.get("projects", [])
    for project in projects:
        create_build_job(project["name"], project["repo_url"], project.get("schedule"))


@kopf.on.update("cforge.steni.us", "v1", "cforge")
def on_update(body, **kwargs):
    """create build jobs for new projects and delete old jobs for removed
    projects.  If there's a change, delete the old job and create a new one
    with the new repo url"""
    spec = body.get("spec", {})
    current_projects = {
        project["name"]: project for project in spec.get("projects", [])
    }

    existing_cronjobs = batch_v1.list_namespaced_cron_job(namespace="cforge")
    # pull the args out of the existing cronjobs that are part of the CForge project object
    existing_cronjobs_dict = {
        cj.metadata.name: {
            "repo_url": cj.spec.job_template.spec.template.spec.containers[0].args[1],
            "schedule": cj.spec.schedule,
        }
        for cj in existing_cronjobs.items
    }

    def cron_job_has_changed(old, new):
        if not new:
            new = DEFAULT_SCHEDULE
        return old != new

    for project_name, project in current_projects.items():
        repo_url = project["repo_url"]
        schedule = project.get("schedule")
        if project_name not in existing_cronjobs_dict:
            create_build_cronjob(project_name, repo_url, schedule)
        # check to see if there's a cronjob with the same name but different settings and recreate if so.
        elif existing_cronjobs_dict[project_name][
            "repo_url"
        ] != repo_url or cron_job_has_changed(
            existing_cronjobs_dict[project_name]["schedule"], schedule
        ):
            delete_build_cronjob(project_name)
            create_build_cronjob(project_name, repo_url, schedule)

    for project_name in existing_cronjobs_dict:
        if project_name not in current_projects:
            delete_build_cronjob(project_name)


@kopf.on.delete("cforge.steni.us", "v1", "cforge")
def on_delete(body, **kwargs):
    spec = body.get("spec", {})
    projects = spec.get("projects", [])
    for project in projects:
        delete_build_cronjob(project["name"])


def get_projects():
    projects = []
    artifact_path = Path(ARTIFACT_DIR)
    if not artifact_path.exists():
        return projects

    for project_dir in artifact_path.iterdir():
        if project_dir.is_dir():
            project = {"name": project_dir.name, "builds": []}
            for build_file in project_dir.iterdir():
                if build_file.suffix == ".log":
                    sha = build_file.stem
                    log_file = build_file
                    tarball = project_dir / f"{sha}.tar.gz"
                    build_status = "success" if tarball.exists() else "failure"
                    project["builds"].append(
                        {
                            "sha": sha,
                            "log_file": f"/artifacts/{project_dir.name}/{log_file.name}",
                            "tarball": (
                                f"/artifacts/{project_dir.name}/{tarball.name}"
                                if tarball.exists()
                                else None
                            ),
                            "status": build_status,
                            "timestamp": log_file.stat().st_mtime,
                        }
                    )
            project["builds"].sort(key=lambda x: x["timestamp"], reverse=True)
            if project["builds"]:
                project["latest_build"] = project["builds"][0]
                projects.append(project)
    return projects


@app.get("/project/{project_name}")
async def read_project(request: Request, project_name: str):
    projects = get_projects()
    for project in projects:
        if project["name"] == project_name:
            return templates.TemplateResponse(
                "project.html", {"request": request, "project": project}
            )
    return {"error": "Project not found"}


@app.get("/")
async def root(request: Request):
    projects = get_projects()
    return templates.TemplateResponse(
        "index.html", {"request": request, "projects": projects}
    )


def run_fastapi():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


def run_kopf():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    kopf.configure(debug=True)
    kopf.run()


if __name__ == "__main__":
    """run FastAPI and Kopf in separate threads"""
    fastapi_thread = threading.Thread(target=run_fastapi)
    kopf_thread = threading.Thread(target=run_kopf)

    fastapi_thread.start()
    kopf_thread.start()

    fastapi_thread.join()
    kopf_thread.join()
