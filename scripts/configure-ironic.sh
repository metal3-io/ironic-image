#!/usr/bin/bash

set -euxo pipefail

IRONIC_EXTERNAL_IP="${IRONIC_EXTERNAL_IP:-}"

# Define the VLAN interfaces to be included in introspection report, e.g.
#   all - all VLANs on all interfaces using LLDP information
#   <interface> - all VLANs on a particular interface using LLDP information
#   <interface.vlan> - a particular VLAN on an interface, not relying on LLDP
export IRONIC_ENABLE_VLAN_INTERFACES=${IRONIC_ENABLE_VLAN_INTERFACES:-${IRONIC_INSPECTOR_VLAN_INTERFACES:-all}}

# shellcheck disable=SC1091
. /bin/tls-common.sh
# shellcheck disable=SC1091
. /bin/ironic-common.sh
# shellcheck disable=SC1091
. /bin/auth-common.sh

export HTTP_PORT=${HTTP_PORT:-80}

if [[ "${IRONIC_USE_MARIADB}" == true ]]; then
    if [[ -z "${MARIADB_PASSWORD:-}" ]]; then
        echo "FATAL: IRONIC_USE_MARIADB requires password, mount a secret under /auth/mariadb"
        exit 1
    fi
    MARIADB_DATABASE=${MARIADB_DATABASE:-ironic}
    MARIADB_USER=${MARIADB_USER:-ironic}
    MARIADB_HOST=${MARIADB_HOST:-127.0.0.1}
    export MARIADB_CONNECTION="mysql+pymysql://${MARIADB_USER}:${MARIADB_PASSWORD}@${MARIADB_HOST}/${MARIADB_DATABASE}?charset=utf8"
    if [[ "$MARIADB_TLS_ENABLED" == "true" ]]; then
        export MARIADB_CONNECTION="${MARIADB_CONNECTION}&ssl=on&ssl_ca=${MARIADB_CACERT_FILE}"
    fi
fi

# zero makes it do cpu number detection on Ironic side
export NUMWORKERS=${NUMWORKERS:-0}


# Whether to enable fast_track provisioning or not
export IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

# Whether cleaning disks before and after deployment
export IRONIC_AUTOMATED_CLEAN=${IRONIC_AUTOMATED_CLEAN:-true}

# Wheter to enable the sensor data collection
export SEND_SENSOR_DATA=${SEND_SENSOR_DATA:-false}

# Set of collectors that should be used with IPA inspection
export IRONIC_IPA_COLLECTORS=${IRONIC_IPA_COLLECTORS:-default,logs}

wait_for_interface_or_ip

# Hostname to use for the current conductor instance.
export IRONIC_CONDUCTOR_HOST=${IRONIC_CONDUCTOR_HOST:-${IRONIC_URL_HOST}}

if [[ -n "$IRONIC_EXTERNAL_IP" ]]; then
    export IRONIC_EXTERNAL_CALLBACK_URL=${IRONIC_EXTERNAL_CALLBACK_URL:-"${IRONIC_SCHEME}://${IRONIC_EXTERNAL_IP}:${IRONIC_ACCESS_PORT}"}
    if [[ "$IRONIC_VMEDIA_TLS_SETUP" == "true" ]]; then
        export IRONIC_EXTERNAL_HTTP_URL=${IRONIC_EXTERNAL_HTTP_URL:-"https://${IRONIC_EXTERNAL_IP}:${VMEDIA_TLS_PORT}"}
    else
        export IRONIC_EXTERNAL_HTTP_URL=${IRONIC_EXTERNAL_HTTP_URL:-"http://${IRONIC_EXTERNAL_IP}:${HTTP_PORT}"}
    fi
fi

IMAGE_CACHE_PREFIX=/shared/html/images/ironic-python-agent
if [[ -z "${DEPLOY_KERNEL_URL:-}" ]] && [[ -z "${DEPLOY_RAMDISK_URL:-}" ]] && \
       [[ -f "${IMAGE_CACHE_PREFIX}.kernel" ]] && [[ -f "${IMAGE_CACHE_PREFIX}.initramfs" ]]; then
    export DEPLOY_KERNEL_URL="file://${IMAGE_CACHE_PREFIX}.kernel"
    export DEPLOY_RAMDISK_URL="file://${IMAGE_CACHE_PREFIX}.initramfs"
fi

declare -A detected_arch
for var_arch in "${!DEPLOY_KERNEL_URL_@}"; do
    IPA_ARCH="${var_arch#DEPLOY_KERNEL_URL}"
    detected_arch["${IPA_ARCH,,}"]=1
done
for file_arch in "${IMAGE_CACHE_PREFIX}"_*.kernel; do
    if [[ -f "${file_arch}" ]]; then
        IPA_ARCH="$(basename "${file_arch#"${IMAGE_CACHE_PREFIX}"_}" .kernel)"
        detected_arch["${IPA_ARCH}"]=1
    fi
done

DEPLOY_KERNEL_BY_ARCH=""
DEPLOY_RAMDISK_BY_ARCH=""
for IPA_ARCH in "${!detected_arch[@]}"; do
    kernel_var="DEPLOY_KERNEL_URL_${IPA_ARCH^^}"
    ramdisk_var="DEPLOY_RAMDISK_URL_${IPA_ARCH^^}"
    if [[ -z "${!kernel_var:-}" ]] && [[ -z "${!ramdisk_var:-}" ]] && \
        [[ -f "${IMAGE_CACHE_PREFIX}_${IPA_ARCH}.kernel" ]] && [[ -f "${IMAGE_CACHE_PREFIX}_${IPA_ARCH}.initramfs" ]]; then
      export "${kernel_var}"="file://${IMAGE_CACHE_PREFIX}_${IPA_ARCH}.kernel"
      export "${ramdisk_var}"="file://${IMAGE_CACHE_PREFIX}_${IPA_ARCH}.initramfs"
    fi
    DEPLOY_KERNEL_BY_ARCH+="${!kernel_var:+${IPA_ARCH}:${!kernel_var},}"
    DEPLOY_RAMDISK_BY_ARCH+="${!ramdisk_var:+${IPA_ARCH}:${!ramdisk_var},}"
done
if [[ -n "${DEPLOY_KERNEL_BY_ARCH}" ]] && [[ -n "${DEPLOY_RAMDISK_BY_ARCH}" ]]; then
    export DEPLOY_KERNEL_BY_ARCH="${DEPLOY_KERNEL_BY_ARCH%?}"
    export DEPLOY_RAMDISK_BY_ARCH="${DEPLOY_RAMDISK_BY_ARCH%?}"
fi

if [[ -f "${IRONIC_CONF_DIR}/ironic.conf" ]]; then
    # Make a copy of the original supposed empty configuration file
    cp "${IRONIC_CONF_DIR}/ironic.conf" "${IRONIC_CONF_DIR}/ironic.conf.orig"
fi

BOOTLOADER_BY_ARCH=""
for bootloader in /templates/uefi_esp_*.img; do
    BOOTLOADER_ARCH="$(basename "${bootloader#/templates/uefi_esp_}" .img)"
    BOOTLOADER_BY_ARCH+="${BOOTLOADER_ARCH}:file://${bootloader},"
done
export BOOTLOADER_BY_ARCH="${BOOTLOADER_BY_ARCH%?}"

# oslo.config also supports Config Opts From Environment, log them to stdout
echo 'Options set from Environment variables'
env | grep "^OS_" || true

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

if [[ -f /proc/sys/crypto/fips_enabled ]]; then
    ENABLE_FIPS_IPA=$(cat /proc/sys/crypto/fips_enabled)
    export ENABLE_FIPS_IPA
fi

# The original ironic.conf is empty, and can be found in ironic.conf_orig
render_j2_config "/etc/ironic/ironic.conf.j2" \
    "${IRONIC_CONF_DIR}/ironic.conf"

configure_json_rpc_auth

# Make sure ironic traffic bypasses any proxies
export NO_PROXY="${NO_PROXY:-},$IRONIC_IP"
