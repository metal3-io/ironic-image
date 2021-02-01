.PHONY: help
help:
	@echo "Targets:"
	@echo "  docker -- build the docker image"

OVERRIDE_DOCKER_IO_REGISTRY ?= "docker.io"

.PHONY: docker
docker:
	docker build --build-arg OVERRIDE_DOCKER_IO_REGISTRY=${OVERRIDE_DOCKER_IO_REGISTRY} . -f Dockerfile
