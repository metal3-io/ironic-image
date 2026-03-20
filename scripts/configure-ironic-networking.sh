#!/usr/bin/bash

set -euxo pipefail

# No need to rely on this being set by whoever created this service since this
# only gets run when ironic-networking is enabled.
export IRONIC_NETWORKING_ENABLED=true

# shellcheck disable=SC1091
. /bin/tls-common.sh
# shellcheck disable=SC1091
. /bin/ironic-common.sh
# shellcheck disable=SC1091
. /bin/ironic-networking-common.sh
# shellcheck disable=SC1091
. /bin/auth-common.sh

# zero makes it do cpu number detection on Ironic side
export NUMWORKERS=${NUMWORKERS:-0}

if [[ -f "${IRONIC_CONF_DIR}/ironic.conf" ]]; then
    # Make a copy of the original supposed empty configuration file
    cp "${IRONIC_CONF_DIR}/ironic.conf" "${IRONIC_CONF_DIR}/ironic.conf.orig"
fi

# The original ironic.conf is empty, and can be found in ironic.conf.orig
render_j2_config "/etc/ironic/ironic-networking.conf.j2" \
    "${IRONIC_CONF_DIR}/ironic.conf"

configure_json_rpc_auth "ironic_networking_json_rpc"

# Make sure ironic traffic bypasses any proxies
export NO_PROXY="${NO_PROXY:-},${IRONIC_IP}"

# Mount point for switch configs
mkdir -p "${IRONIC_NETWORKING_DRIVER_CONFIG_DIR}"
