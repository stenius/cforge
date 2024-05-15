## RFC: CForge - A Simple Build Server for C Programs

### Overview

This RFC outlines the design and implementation of CForge, a simple build server and artifact repository for C programs. CForge will register, build, and store artifacts for C programs written in ISO C99, tracked in Git repositories. Additionally, it will periodically fetch new commits, build them, and display the status of builds on a web page.

### Assumptions

- A “C program” consists of .c and .h files and a Makefile with canonical `all` and `clean` targets.
- The C program only depends on the C standard library and builds into a single executable.
- The C program is tracked in a Git repository.

### Goals

1. **Registering & Building C Programs**
   - Support registration and building of multiple independent C programs.
   - Detect and report build failures.

2. **Simple Artifact Repository**
   - Store build artifacts tied to specific commits in the program's Git repository.

3. **Periodic Builds**
   - Automatically fetch new commits periodically and build them.

4. **Web Page Showing C Programs & Their Statuses**
   - Display the status of current and previous builds on a simple webpage.

### Design

#### Kubernetes Architecture

- **Build Jobs**: Kubernetes Jobs will handle the building of C programs.
- **Artifact Repository**: A Kubernetes volume mount will store build artifacts as tarballs.
- **Config File Watcher**: A Kubernetes service will watch a configuration file for changes and create build jobs.
- **Periodic Builds**: Kubernetes CronJobs will periodically fetch new commits and trigger builds.
- **Web Server**: A Kubernetes service will serve a basic HTTP page displaying build statuses and logs.

#### Detailed Components

1. **Build Program**
   - Takes a public Git URL and writes a tarball with the repository path and SHA in its name to the artifact repository.
   - Runs as a Kubernetes Job started by the config file watcher or a Kubernetes CronJob.
   - The build job will run a pod that uses a Debian container with the `build-essential` package, which contains necessary compilers and make tools.

2. **Artifact Repository**
   - Artifacts will be stored as tarballs in a Kubernetes volume mount.
   - Tarball names will include the repository path and commit SHA.

3. **Config File Watcher**
   - Watches a configuration file for changes.
   - Creates Kubernetes Jobs for new or updated C programs.
   - Serves a basic HTTP page displaying build statuses.

4. **Periodic Builds**
   - Kubernetes CronJobs will periodically fetch new commits from registered repositories.
   - Trigger builds for new commits.

5. **Web Server**
   - Displays the current and previous builds for C projects.
   - Shows the status of builds (completed, failed, building, etc.).
   - Provides links to failure logs for failed builds.

### Implementation Plan

1. **Build Program**
   - Develop a program to clone a Git repository, build the C program, and create a tarball of the build artifact and the build logs.
   - Ensure the build job runs in a Debian container with the `build-essential` package.
  
2. **Artifact Repository**
   - Configure a Kubernetes volume mount to store build artifacts.

3. **Config File Watcher Service**
   - Implement a service to watch the configuration file and create build jobs.
   - Develop the HTTP server to display build statuses and logs.

4. **Periodic Builds**
   - Set up Kubernetes CronJobs to fetch new commits and trigger builds periodically.


### Example Workflow

1. **Registering a C Program**
   - The config file is updated with the new C program's Git URL.
   - The config file watcher detects the change and creates a build job.
   - The build job clones the repository, builds the program using the Debian container with `build-essential`, and stores the artifact in the repository.

2. **Handling Build Failures**
   - If a build fails, the failure is logged, and the status is shown on the web page.
   - The web page provides a link to the failure log.

3. **Periodic Builds**
   - Kubernetes CronJobs fetch new commits periodically.
   - Artifacts are stored, and statuses are updated on the web page.

### Conclusion

This design provides a scalable and autonomous build server for C programs using Kubernetes. CForge handles the registration, building, and storage of artifacts, supports periodic builds, and displays build statuses on a web page. By using Debian containers with the `build-essential` package, CForge ensures a consistent and reliable build environment.
