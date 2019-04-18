.PHONY: help
help:
	@echo "Targets:"
	@echo "  docker -- build the docker image"

.PHONY: docker
docker:
	docker build . -f Dockerfile
