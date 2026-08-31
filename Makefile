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

# Provide a GitHub token explicitly to generate release notes, e.g.:
#   RELEASE_NOTES_TOKEN="$(gh auth token)" make release-notes
# It is passed to the tool through a scoped environment variable (not a CLI
# flag) so the secret is not exposed in process arguments or CI logs. This is
# intentionally separate from the ambient GITHUB_TOKEN so that delegating a
# credential to this tool is a deliberate choice. If unset, the tool falls back
# to the GITHUB_TOKEN environment variable (deprecated).
RELEASE_NOTES_TOKEN ?=

.PHONY: release-notes
release-notes: $(RELEASE_NOTES_DIR) $(RELEASE_NOTES)
	@cd hack/tools && RELEASE_NOTES_TOKEN="$(RELEASE_NOTES_TOKEN)" $(GO) run release/notes.go $(RELEASE_NOTES_ARGS) > $(realpath $(RELEASE_NOTES_DIR))/$(RELEASE_TAG).md
