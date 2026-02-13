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

# Save and load the image into the cluster
IMAGE_ARCHIVE="$(mktemp --suffix=.tar)"
"${CONTAINER_RUNTIME}" save "${IRONIC_CUSTOM_IMAGE}" > "${IMAGE_ARCHIVE}"

if [[ "${CLUSTER_TYPE}" == "kind" ]]; then
    kind load image-archive -v 2 "${IMAGE_ARCHIVE}"
else
    minikube image load --logtostderr "${IMAGE_ARCHIVE}"
fi
rm -f "${IMAGE_ARCHIVE}"

# Create a custom e2e overlay for ironic-image testing
CUSTOM_OVERLAY_DIR="${BMO_ROOT}/test/e2e/data/ironic-standalone-operator/ironic/overlays/ironic-image-e2e"
mkdir -p "${CUSTOM_OVERLAY_DIR}"

# Create kustomization.yaml that uses the e2e overlay as base
cat > "${CUSTOM_OVERLAY_DIR}/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: baremetal-operator-system

resources:
  - ../e2e

patches:
  - path: ironic-custom-image.yaml
EOF

# Create patch to override the ironic image
cat > "${CUSTOM_OVERLAY_DIR}/ironic-custom-image.yaml" <<EOF
apiVersion: ironic.openstack.org/v1alpha1
kind: Ironic
metadata:
  name: ironic
  namespace: baremetal-operator-system
spec:
  images:
    ironic: "${IRONIC_CUSTOM_IMAGE}"
EOF

# Update the BMO e2e configuration to use our custom overlay
E2E_CONFIG="${BMO_ROOT}/test/e2e/config/ironic.yaml"
if [[ -f "${E2E_CONFIG}" ]]; then
    # Backup original config
    cp "${E2E_CONFIG}" "${E2E_CONFIG}.bak"

    # Replace the kustomization path to use our custom overlay
    sed -i 's|data/ironic-standalone-operator/ironic/overlays/e2e|data/ironic-standalone-operator/ironic/overlays/ironic-image-e2e|g' "${E2E_CONFIG}"
fi

# Run the BMO e2e tests
cd "${BMO_ROOT}" || exit 1
echo "Running BMO e2e tests with custom ironic image: ${IRONIC_CUSTOM_IMAGE}"
./hack/ci-e2e.sh
