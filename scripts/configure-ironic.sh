#!/usr/bin/bash

set -euxo pipefail

IRONIC_EXTERNAL_IP="${IRONIC_EXTERNAL_IP:-}"

# Define the VLAN interfaces to be included in introspection report, e.g.
#   all - all VLANs on all interfaces using LLDP information
#   <interface> - all VLANs on a particular interface using LLDP information
#   <interface.vlan> - a particular VLAN on an interface, not relying on LLDP
export IRONIC_ENABLE_VLAN_INTERFACES=${IRONIC_ENABLE_VLAN_INTERFACES:-all}

# shellcheck disable=SC1091
. /bin/tls-common.sh
# shellcheck disable=SC1091
. /bin/ironic-common.sh
# shellcheck disable=SC1091
. /bin/auth-common.sh

export HTTP_PORT=${HTTP_PORT:-80}

MARIADB_PASSWORD=${MARIADB_PASSWORD:-change_me}
MARIADB_DATABASE=${MARIADB_DATABASE:-ironic}
MARIADB_USER=${MARIADB_USER:-ironic}
MARIADB_HOST=${MARIADB_HOST:-127.0.0.1}
export MARIADB_CONNECTION="mysql+pymysql://${MARIADB_USER}:${MARIADB_PASSWORD}@${MARIADB_HOST}/${MARIADB_DATABASE}?charset=utf8"
if [[ "$MARIADB_TLS_ENABLED" == "true" ]]; then
    export MARIADB_CONNECTION="${MARIADB_CONNECTION}&ssl=on&ssl_ca=${MARIADB_CACERT_FILE}"
fi

# TODO(dtantsur): remove the explicit default once we get
# https://review.opendev.org/761185 in the repositories
NUMPROC="$(grep -c "^processor" /proc/cpuinfo)"
if [[ "$NUMPROC" -lt 4 ]]; then
    NUMPROC=4
fi
export NUMWORKERS=${NUMWORKERS:-$NUMPROC}

export IRONIC_USE_MARIADB=${IRONIC_USE_MARIADB:-true}

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

export IRONIC_BASE_URL=${IRONIC_BASE_URL:-"${IRONIC_SCHEME}://${IRONIC_URL_HOST}:${IRONIC_ACCESS_PORT}"}

if [[ -n "$IRONIC_EXTERNAL_IP" ]]; then
    export IRONIC_EXTERNAL_CALLBACK_URL=${IRONIC_EXTERNAL_CALLBACK_URL:-"${IRONIC_SCHEME}://${IRONIC_EXTERNAL_IP}:${IRONIC_ACCESS_PORT}"}
    if [[ "$IRONIC_VMEDIA_TLS_SETUP" == "true" ]]; then
        export IRONIC_EXTERNAL_HTTP_URL=${IRONIC_EXTERNAL_HTTP_URL:-"https://${IRONIC_EXTERNAL_IP}:${VMEDIA_TLS_PORT}"}
    else
        export IRONIC_EXTERNAL_HTTP_URL=${IRONIC_EXTERNAL_HTTP_URL:-"http://${IRONIC_EXTERNAL_IP}:${HTTP_PORT}"}
    fi
fi

IMAGE_CACHE_PREFIX=/shared/html/images/ironic-python-agent
if [[ -f "${IMAGE_CACHE_PREFIX}.kernel" ]] && [[ -f "${IMAGE_CACHE_PREFIX}.initramfs" ]]; then
    export IRONIC_DEFAULT_KERNEL="${IMAGE_CACHE_PREFIX}.kernel"
    export IRONIC_DEFAULT_RAMDISK="${IMAGE_CACHE_PREFIX}.initramfs"
fi

if [[ -f /etc/ironic/ironic.conf ]]; then
    # Make a copy of the original supposed empty configuration file
    cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig
fi

# oslo.config also supports Config Opts From Environment, log them to stdout
echo 'Options set from Environment variables'
env | grep "^OS_" || true

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

configure_json_rpc_auth

. /bin/coreos-ipa-common.sh

if [[ -f /proc/sys/crypto/fips_enabled ]]; then
    ENABLE_FIPS_IPA=$(cat /proc/sys/crypto/fips_enabled)
    export ENABLE_FIPS_IPA
fi

# The original ironic.conf is empty, and can be found in ironic.conf_orig
render_j2_config /etc/ironic/ironic.conf.j2 /etc/ironic/ironic.conf

configure_client_basic_auth ironic-rpc

# Make sure ironic traffic bypasses any proxies
export NO_PROXY="${NO_PROXY:-},$IRONIC_IP"

PROBE_CURL_ARGS=
if [[ "${IRONIC_REVERSE_PROXY_SETUP}" == "true" ]]; then
    if [[ "${IRONIC_PRIVATE_PORT}" == "unix" ]]; then
        PROBE_URL="http://127.0.0.1:6385"
        PROBE_CURL_ARGS="--unix-socket /shared/ironic.sock"
    else
        PROBE_URL="http://127.0.0.1:${IRONIC_PRIVATE_PORT}"
    fi
else
        PROBE_URL="${IRONIC_BASE_URL}"
fi
export PROBE_CURL_ARGS
export PROBE_URL

PROBE_KIND=readiness render_j2_config /bin/ironic-probe.j2 /bin/ironic-readiness
PROBE_KIND=liveness render_j2_config /bin/ironic-probe.j2 /bin/ironic-liveness
