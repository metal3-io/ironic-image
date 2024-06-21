SHELL=/usr/bin/env bash -o errexit

.PHONY: help build

export CONTAINER_ENGINE ?= podman

help:
	@echo "Targets:"
	@echo "  build -- build the docker image"

build:
	$(CONTAINER_ENGINE) build . -f Dockerfile

