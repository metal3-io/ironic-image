#!/usr/bin/env bash

set -eux -o pipefail

REPO_ROOT=$(realpath "$(dirname "${BASH_SOURCE[0]}")/..")
cd "${REPO_ROOT}" || exit 1

CLUSTER_TYPE="${CLUSTER_TYPE:-kind}"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-docker}"
IRONIC_CUSTOM_IMAGE="${IRONIC_CUSTOM_IMAGE:-localhost/ironic:bmo-e2e}"
BMO_ROOT="${REPO_ROOT}/../baremetal-operator"

# Build the ironic image
echo "Building ironic image: ${IRONIC_CUSTOM_IMAGE}"
"${CONTAINER_RUNTIME}" build -t "${IRONIC_CUSTOM_IMAGE}" .

# Copy our custom e2e configuration to BMO
E2E_CONFIG_SRC="${REPO_ROOT}/test/e2e/config/ironic.yaml"
E2E_CONFIG_DST="${BMO_ROOT}/test/e2e/config/ironic.yaml"
if [[ -f "${E2E_CONFIG_SRC}" ]]; then
    # Backup original config
    cp "${E2E_CONFIG_DST}" "${E2E_CONFIG_DST}.bak"

    # Copy our custom config
    cp "${E2E_CONFIG_SRC}" "${E2E_CONFIG_DST}"
fi

# Run the BMO e2e tests
cd "${BMO_ROOT}" || exit 1
echo "Running BMO e2e tests with custom ironic image: ${IRONIC_CUSTOM_IMAGE}"
./hack/ci-e2e.sh
