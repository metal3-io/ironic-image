#!/usr/bin/env bash

set -eux -o pipefail

REPO_ROOT=$(realpath "$(dirname "${BASH_SOURCE[0]}")/..")
cd "${REPO_ROOT}" || exit 1

CLUSTER_TYPE="${CLUSTER_TYPE:-kind}"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-podman}"
IRONIC_CUSTOM_IMAGE=${IRONIC_CUSTOM_IMAGE:-localhost/ironic:test}

declare -a build_args
declare -a to_delete

if [[ -n "${IRONIC_SOURCE:-}" ]]; then
    if [[ -d "${IRONIC_SOURCE}" ]]; then
        cp -ra "${IRONIC_SOURCE}" sources/ironic
        rm -rf sources/ironic/.tox
        to_delete+=(sources/ironic)
    fi
    build_args+=(--build-arg IRONIC_SOURCE=ironic)
fi
if [[ -n "${SUSHY_SOURCE:-}" ]]; then
    if [[ -d "${SUSHY_SOURCE}" ]]; then
        cp -ra "${SUSHY_SOURCE}" sources/sushy
        rm -rf sources/sushy/.tox
        to_delete+=(sources/sushy)
    fi
    build_args+=(--build-arg SUSHY_SOURCE=sushy)
fi

"${CONTAINER_RUNTIME}" build -t "${IRONIC_CUSTOM_IMAGE}" "${build_args[@]}" .

IMAGE_ARCHIVE="$(mktemp --suffix=.tar)"
"${CONTAINER_RUNTIME}" save "${IRONIC_CUSTOM_IMAGE}" > "${IMAGE_ARCHIVE}"
to_delete+=("${IMAGE_ARCHIVE}")

if [[ "${CLUSTER_TYPE}" == "kind" ]]; then
    kind load image-archive -v 2 "${IMAGE_ARCHIVE}"
else
    minikube image load --logtostderr "${IMAGE_ARCHIVE}"
fi
rm -rf "${to_delete[@]}"
