# CForge

CForge is a simple build server and artifact repository for C programs written in ISO C99. It registers, builds, and stores artifacts for C programs tracked in Git repositories. CForge can periodically fetch new commits, build them, and display the status of builds on a web page.


## Features

- **Register and Build C Programs**: Supports multiple independent C programs. Detects and reports build failures.
- **Artifact Repository**: Stores build artifacts tied to specific commits.
- **Periodic Builds**: Automatically fetches new commits periodically and builds them.
- **Web Page**: Displays the status of current and previous builds.
![Project Listing](docs/projects_root.png?raw=true)
![Project Details](docs/project_details.png?raw=true)

## Assumptions

- A "C program" consists of `.c` and `.h` files and a Makefile with canonical `all` and `clean` targets.
- The C program only depends on the C standard library and builds into a single executable.
- The C program is tracked in a Git repository.

## Architecture

CForge uses Kubernetes to manage build jobs, artifact storage, and web services.

![Kubernetes Architecture](docs/kubernetes_arch.png?raw=true)

### Components

1. **Build Jobs**
   - Kubernetes Jobs handle the building of C programs.
   - Build jobs run in a pod using a Debian container with the `build-essential` package.

2. **Artifact Repository**
   - Artifacts are stored as tarballs in a Kubernetes volume mount.
   - Tarball names include the project name and commit SHA.
   - Build logs are stored along side the tarballs.

3. **Config File Watcher**
   - A Kubernetes service watches a configuration file for changes and creates build jobs.
   - Also serves a basic HTTP page displaying build statuses.
      - Displays the current and previous builds for projects.
      - Shows the status of builds (completed, failed).
      - Provides links to logs for builds.

4. **Periodic Builds**
   - Kubernetes CronJobs fetch new commits periodically and trigger builds.

## Getting Started

### Prerequisites

- Kubernetes cluster that supports persistent volumes
- Docker
- Git

### Setup

1. **Clone the Repository**

   ```sh
   git clone https://github.com/stenius/cforge
   cd cforge
   ```

2. **Build Docker Image**

   Build and publish the Docker images for the build job and the server/operator:

   ```sh
   make
   ```

3. **Deploy to Kubernetes**

   Apply the Kubernetes manifests to deploy CForge:

   ```sh
   kubectl apply -f k8s/
   ```

4. **Update Configuration File**

   Create and apply a 'CForge' custom resource with your project details.

   ```yaml
   apiVersion: cforge.steni.us/v1
   kind: CForge
   metadata:
     name: cforge
     namespace: cforge
   spec:
     projects:
     - name: helloworld
       repo_url: https://github.com/laristra/c-makefile.git
     - name: job2
       repo_url: https://github.com/laristra/c-makefile.git

   ```


### Using CForge

1. **Register a C Program**

   Add the Git URL of the C program to the `config.yaml` file.

   ```yaml
   - name: hello
     url: https://github.com/user/hello.git
   ```

   The config file watcher will detect the change and create a build job.

2. **View Build Status**

   Access the web page served by the config file watcher to view the status of builds:

   ```
   http://<service-ip>:<port>
   ```

   The page displays the current and previous builds for the registered C programs and provides links to failure logs for failed builds.

## Contributing

Contributions are **NOT** welcome! **This is a toy project**. Please fork the repository.

## License

This project is licensed under the BSD License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

CForge uses the following open-source projects:

- [Kubernetes](https://kubernetes.io/)
- [Debian](https://www.debian.org/)
- [Kopf](https://kopf.readthedocs.io/)
