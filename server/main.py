import asyncio
import json
import threading

import kopf
from fastapi import FastAPI, Request
from kubernetes import client, config

app = FastAPI()

try:
    # Load Kubernetes config
    config.load_kube_config()
except config.config_exception.ConfigException:
    # Load incluster config
    config.load_incluster_config()

k8s_client = client.ApiClient()
batch_v1 = client.BatchV1Api(k8s_client)


def create_k8s_job(job_name, repo_url):
    """create a kubernetes job that attaches the artifact volume"""
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name=job_name,
                            image="ghcr.io/stenius/cforge/builder:latest",
                            args=[repo_url],
                            volume_mounts=[
                                client.V1VolumeMount(
                                    name="artifacts", mount_path="/mnt/data"
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
            )
        ),
    )
    batch_v1.create_namespaced_job(namespace="cforge", body=job)


def delete_k8s_job(job_name):
    batch_v1.delete_namespaced_job(
        name=job_name,
        namespace="cforge",
        body=client.V1DeleteOptions(propagation_policy="Foreground"),
    )


# Kopf handler for the creation of CRD instances
@kopf.on.create("cforge.steni.us", "v1", "cforge")
def on_create(body, **kwargs):
    spec = body.get("spec", {})
    items = spec.get("items", [])
    for item in items:
        create_k8s_job(item["name"], item["repo_url"])


@kopf.on.update("cforge.steni.us", "v1", "cforge")
def on_update(body, **kwargs):
    """create build jobs for new projects and delete old jobs for removed
    projects.  If there's a change, delete the old job and create a new one
    with the new repo url"""
    spec = body.get("spec", {})
    current_items = {
        project["name"]: project["repo_url"] for project in spec.get("projects", [])
    }

    existing_jobs = batch_v1.list_namespaced_job(namespace="cforge")
    existing_jobs_dict = {
        job.metadata.name: job.spec.template.spec.containers[0].args[0]
        for job in existing_jobs.items
    }

    for project_name, repo_url in current_items.items():
        if project_name not in existing_jobs_dict:
            create_k8s_job(project_name, repo_url)
        elif existing_jobs_dict[project_name] != repo_url:
            delete_k8s_job(project_name)
            create_k8s_job(project_name, repo_url)

    for job_name in existing_jobs_dict:
        if job_name not in current_items:
            delete_k8s_job(job_name)


@kopf.on.delete("cforge.steni.us", "v1", "cforge")
def on_delete(body, **kwargs):
    spec = body.get("spec", {})
    items = spec.get("projects", [])
    for item in items:
        delete_k8s_job(item["name"])


@app.get("/")
async def root():
    return {"Hello": "World!"}


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
