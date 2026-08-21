SHELL=/usr/bin/env bash -o errexit

.PHONY: help build

export CONTAINER_ENGINE ?= podman

help:
	@echo "Targets:"
	@echo "  build -- build the docker image"

build:
	$(CONTAINER_ENGINE) build . -f Dockerfile

## --------------------------------------
## Release
## --------------------------------------
GO := $(shell type -P go)
# Use GOPROXY environment variable if set
GOPROXY := $(shell $(GO) env GOPROXY)
ifeq ($(GOPROXY),)
GOPROXY := https://proxy.golang.org
endif
export GOPROXY

RELEASE_TAG ?= $(shell git describe --abbrev=0 2>/dev/null)
PREVIOUS_RELEASE_TAG ?=
RELEASE_NOTES_DIR := releasenotes

$(RELEASE_NOTES_DIR):
	mkdir -p $(RELEASE_NOTES_DIR)/

RELEASE_NOTES_ARGS := --releaseTag=$(RELEASE_TAG)
ifneq ($(PREVIOUS_RELEASE_TAG),)
RELEASE_NOTES_ARGS += --previousReleaseTag=$(PREVIOUS_RELEASE_TAG)
endif

.PHONY: release-notes
release-notes: $(RELEASE_NOTES_DIR) $(RELEASE_NOTES)
	@echo "Generating release notes for $(RELEASE_TAG)..."
	@cd hack/tools && $(GO) run release/notes.go $(RELEASE_NOTES_ARGS) \
	--githubToken="$(GITHUB_TOKEN)" > $(realpath $(RELEASE_NOTES_DIR))/$(RELEASE_TAG).md
	@echo "Release notes generated at $(RELEASE_NOTES_DIR)/$(RELEASE_TAG).md"
