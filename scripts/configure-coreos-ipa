#!/usr/bin/bash

. /bin/ironic-common.sh
. /bin/coreos-ipa-common.sh

# Base64 encoded pull secret
export IRONIC_AGENT_PULL_SECRET=${IRONIC_AGENT_PULL_SECRET:-}

set -x

export IRONIC_INSPECTOR_VLAN_INTERFACES=${IRONIC_INSPECTOR_VLAN_INTERFACES:-all}
export IRONIC_AGENT_IMAGE
export IRONIC_AGENT_PODMAN_FLAGS=${IRONIC_AGENT_PODMAN_FLAGS:---tls-verify=false}

IRONIC_CERT_FILE=/certs/ironic/tls.crt

wait_for_interface_or_ip

if [ -f "$IRONIC_CERT_FILE" ]; then
    export IRONIC_BASE_URL="https://${IRONIC_URL_HOST}"
else
    export IRONIC_BASE_URL="http://${IRONIC_URL_HOST}"
fi

render_j2_config /tmp/ironic-python-agent.ign.j2 "$IGNITION_FILE"
# Print the generated ignition for debugging purposes.
cat "$IGNITION_FILE" | sed '/authfile/,+1 s/data:.*"/<redacted>"/'

if [ -f "$ISO_FILE" ]; then
    coreos-installer iso ignition embed -i "$IGNITION_FILE" -f "$ISO_FILE"
fi
