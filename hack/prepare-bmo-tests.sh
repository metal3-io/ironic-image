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

# Create a custom kustomize overlay in BMO that uses our image.
# This avoids duplicating BMO's entire e2e config - we only override the ironic image.
# TODO: Propose to BMO to accept IRONIC_IMAGE_OVERRIDE env var to simplify this further.
# See: https://github.com/metal3-io/baremetal-operator/commit/b35cccb8 for their
# recent refactoring that moved image overrides to kustomize overlays.
CUSTOM_OVERLAY="${BMO_ROOT}/test/e2e/data/ironic-standalone-operator/ironic/overlays/ironic-image-custom"
mkdir -p "${CUSTOM_OVERLAY}"

cat > "${CUSTOM_OVERLAY}/kustomization.yaml" <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
- ../e2e
patches:
- target:
    kind: Ironic
  patch: |-
    - op: replace
      path: /spec/images/ironic
      value: ${IRONIC_CUSTOM_IMAGE}
EOF

# Patch BMO's e2e config to add our custom image and use our overlay.
# We only modify what's necessary - everything else uses BMO's defaults.
BMO_CONFIG="${BMO_ROOT}/test/e2e/config/ironic.yaml"
cp "${BMO_CONFIG}" "${BMO_CONFIG}.bak"

# Add our custom image to the images list (after the BMO e2e image loadBehavior line)
sed -i '/name: quay.io\/metal3-io\/baremetal-operator:e2e/,/loadBehavior:/{
  /loadBehavior:/a\
# Use custom ironic-image build\
- name: '"${IRONIC_CUSTOM_IMAGE}"'\
  loadBehavior: tryLoad
}' "${BMO_CONFIG}"

# Add our custom kustomization path to the variables section
sed -i '/NAMESPACE_SCOPED:/a\
  # Use custom ironic-image overlay\
  IRONIC_KUSTOMIZATION: "data/ironic-standalone-operator/ironic/overlays/ironic-image-custom"' "${BMO_CONFIG}"

# Run the BMO e2e tests
cd "${BMO_ROOT}" || exit 1
echo "Running BMO e2e tests with custom ironic image: ${IRONIC_CUSTOM_IMAGE}"
export GINKGO_FOCUS=""
./hack/ci-e2e.sh
