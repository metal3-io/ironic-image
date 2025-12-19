#!/usr/bin/bash

set -euxo pipefail

# This script builds Python wheels for all Ironic dependencies.
# It runs in the wheel-builder stage of the Docker build.

UPPER_CONSTRAINTS_PATH="/tmp/${UPPER_CONSTRAINTS_FILE:-}"

# If the content of the upper-constraints file is empty,
# we assume we're on the master branch
if [[ ! -s "${UPPER_CONSTRAINTS_PATH}" ]]; then
    UPPER_CONSTRAINTS_PATH="/tmp/upper-constraints.txt"
    curl -L https://releases.openstack.org/constraints/upper/master -o "${UPPER_CONSTRAINTS_PATH}"
fi

# Install build dependencies
python3.12 -m pip install --no-cache-dir pip=="${PIP_VERSION}" setuptools=="${SETUPTOOLS_VERSION}" wheel jinja2

# Allow override via environment variable (used by deps-wheel-builder stage)
IRONIC_PKG_LIST="${IRONIC_PKG_LIST:-/tmp/ironic-packages-list}"
IRONIC_PKG_LIST_FINAL="/tmp/ironic-packages-list-final"

# Render the Jinja2 template for the package list
python3.12 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ, path=os.path))' < "${IRONIC_PKG_LIST}" > "${IRONIC_PKG_LIST_FINAL}"

# Remove sushy constraint if building from source
if [[ -n ${SUSHY_SOURCE:-} ]]; then
    sed -i '/^sushy===/d' "${UPPER_CONSTRAINTS_PATH}"
fi

# Build wheels for all packages
# Note: some packages may not produce wheels (pure Python), but pip wheel handles this
python3.12 -m pip wheel \
    --wheel-dir=/wheels \
    --no-cache-dir \
    -r "${IRONIC_PKG_LIST_FINAL}" \
    -c "${UPPER_CONSTRAINTS_PATH}"

echo "Wheels built successfully in /wheels"
ls -la /wheels/
