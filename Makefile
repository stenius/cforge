# Define variables
IMAGE_NAME_BUILDER=ghcr.io/stenius/cforge/builder
IMAGE_NAME_SERVER=ghcr.io/stenius/cforge/server
TAG=latest

# Define Docker build, tag, and push commands
DOCKER_BUILD=docker build
DOCKER_TAG=docker tag
DOCKER_PUSH=docker push

.PHONY: all build-builder build-server push-builder push-server

# Default target
all: build-builder build-server push-builder push-server

# Build cforge-builder Docker image
build-builder:
	$(DOCKER_BUILD) -t $(IMAGE_NAME_BUILDER):$(TAG) ./builder

# Build the cforge-server docker image
build-server:
	$(DOCKER_BUILD) -t $(IMAGE_NAME_SERVER):$(TAG) ./server

push-builder:
	$(DOCKER_PUSH) $(IMAGE_NAME_BUILDER):$(TAG)

push-server:
	$(DOCKER_PUSH) $(IMAGE_NAME_SERVER):$(TAG)

# Clean up Docker images
clean:
	docker rmi $(IMAGE_NAME_BUILDER):$(TAG) $(IMAGE_NAME_SERVER):$(TAG)
