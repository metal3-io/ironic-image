.PHONY: build-ocp

build-ocp:
	podman build -f Dockerfile.ocp

.PHONY: check-reqs

check-reqs:
	./tools/check-requirements.sh

