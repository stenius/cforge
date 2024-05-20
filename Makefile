# Define variables
BUILDER_IMAGE_NAME=steni.us/builder
IMAGE_NAME2=myrepo/myimage2
TAG=latest

# Define Docker build, tag, and push commands
DOCKER_BUILD=docker build
DOCKER_TAG=docker tag
DOCKER_PUSH=docker push

.PHONY: all builder build2 push1 push2

# Default target
all: builder build2 push1 push2

# Build the "builder" Docker image
builder:
	$(DOCKER_BUILD) -t $(BUILDER_IMAGE_NAME):$(TAG) ./builder

# Build the second Docker image
build2:
	$(DOCKER_BUILD) -t $(IMAGE_NAME2):$(TAG) ./builder2

# Push the first Docker image to the repository
push1:
	$(DOCKER_PUSH) $(IMAGE_NAME1):$(TAG)

# Push the second Docker image to the repository
push2:
	$(DOCKER_PUSH) $(IMAGE_NAME2):$(TAG)

# Clean up Docker images
clean:
	docker rmi $(IMAGE_NAME1):$(TAG) $(IMAGE_NAME2):$(TAG)
