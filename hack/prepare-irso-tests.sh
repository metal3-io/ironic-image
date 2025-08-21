#!/usr/bin/env bash

set -eux -o pipefail

REPO_ROOT=$(realpath "$(dirname "${BASH_SOURCE[0]}")/..")
cd "${REPO_ROOT}" || exit 1

CLUSTER_TYPE="${CLUSTER_TYPE:-kind}"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-podman}"
IRONIC_CUSTOM_IMAGE=${IRONIC_CUSTOM_IMAGE:-localhost/ironic:test}

"${CONTAINER_RUNTIME}" build -t "${IRONIC_CUSTOM_IMAGE}" .
IMAGE_ARCHIVE="$(mktemp --suffix=.tar)"
"${CONTAINER_RUNTIME}" save "${IRONIC_CUSTOM_IMAGE}" > "${IMAGE_ARCHIVE}"
if [[ "${CLUSTER_TYPE}" == "kind" ]]; then
    kind load image-archive -v 2 "${IMAGE_ARCHIVE}"
else
    minikube image load --logtostderr "${IMAGE_ARCHIVE}"
fi
rm -f "${IMAGE_ARCHIVE}"
