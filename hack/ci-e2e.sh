#!/usr/bin/env bash

set -eux -o pipefail

REPO_ROOT=$(realpath "$(dirname "${BASH_SOURCE[0]}")/..")
cd "${REPO_ROOT}" || exit 1

CLUSTER_TYPE="${CLUSTER_TYPE:-kind}"

IRSO_REPO="${IRSO_REPO:-https://github.com/metal3-io/ironic-standalone-operator}"
IRSO_BRANCH="${IRSO_BRANCH:-main}"
if [[ -z "${IRSO_PATH:-}" ]]; then
    IRSO_PATH="$(mktemp -td irso-XXXXXXXX)"
    git clone "${IRSO_REPO}" -b "${IRSO_BRANCH}" "${IRSO_PATH}"
fi
export IRONIC_CUSTOM_IMAGE=localhost/ironic:test

if [[ "${CLUSTER_TYPE}" == kind ]]; then
    podman build -t "${IRONIC_CUSTOM_IMAGE}" .

    archive="$(mktemp --suffix=.tar)"
    podman save "${IRONIC_CUSTOM_IMAGE}" > "${archive}"
    kind load image-archive -v 2 "${archive}"
    rm -f "${archive}"
else
    minikube image build -t "${IRONIC_CUSTOM_IMAGE}" .
fi

cd "${IRSO_PATH}/test"
# shellcheck disable=SC1091
. testing.env
export IRONIC_CUSTOM_VERSION=latest

exec go test -timeout 60m
