#!/usr/bin/bash

ROOTFS_FILE=${ROOTFS_FILE:-/shared/html/images/ironic-python-agent.rootfs}
IGNITION_FILE=${IGNITION_FILE:-/shared/html/ironic-python-agent.ign}
ISO_FILE=${ISO_FILE:-/shared/html/images/ironic-python-agent.iso}

function coreos_kernel_params {
    echo -n "coreos.live.rootfs_url=http://${IRONIC_URL_HOST}:$HTTP_PORT/images/ironic-python-agent.rootfs"
    if [ -f "$IGNITION_FILE" ]; then
        echo -n " ignition.config.url=http://${IRONIC_URL_HOST}:$HTTP_PORT/ironic-python-agent.ign"
    fi
    echo " ignition.firstboot ignition.platform.id=metal"
}

function use_coreos_ipa {
    [ -f "$ROOTFS_FILE" ] && return 0 || return 1
}

if use_coreos_ipa; then
    export IRONIC_KERNEL_PARAMS="${IRONIC_KERNEL_PARAMS:-} $(coreos_kernel_params)"
fi
