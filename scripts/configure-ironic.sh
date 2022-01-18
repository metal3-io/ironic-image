#!/usr/bin/bash

# Define the VLAN interfaces to be included in introspection report, e.g.
#   all - all VLANs on all interfaces using LLDP information
#   <interface> - all VLANs on a particular interface using LLDP information
#   <interface.vlan> - a particular VLAN on an interface, not relying on LLDP
export IRONIC_INSPECTOR_VLAN_INTERFACES=${IRONIC_INSPECTOR_VLAN_INTERFACES:-all}
SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

. "${SCRIPTDIR}/tls-common.sh"
. "${SCRIPTDIR}/ironic-common.sh"

export HTTP_PORT=${HTTP_PORT:-"80"}
export MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
# TODO(dtantsur): remove the explicit default once we get
# https://review.opendev.org/761185 in the repositories
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMPROC=$(( NUMPROC <= 4 ? NUMPROC : 4 ))
export NUMWORKERS=${NUMWORKERS:-$NUMPROC}

export IRONIC_USE_MARIADB=${IRONIC_USE_MARIADB:-true}
export IRONIC_EXPOSE_JSON_RPC=${IRONIC_EXPOSE_JSON_RPC:-true}

# Whether to enable fast_track provisioning or not
export IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

# Whether cleaning disks before and after deployment
export IRONIC_AUTOMATED_CLEAN=${IRONIC_AUTOMATED_CLEAN:-true}

# Wheter to enable the sensor data collection
export SEND_SENSOR_DATA=${SEND_SENSOR_DATA:-false}

wait_for_interface_or_ip

export IRONIC_BASE_URL="${IRONIC_SCHEME}://${IRONIC_URL_HOST}:6385"
export IRONIC_INSPECTOR_BASE_URL="${IRONIC_INSPECTOR_SCHEME}://${IRONIC_URL_HOST}:5050"

if [ ! -z "${IRONIC_EXTERNAL_IP}" ]; then
    export IRONIC_EXTERNAL_CALLBACK_URL="${IRONIC_SCHEME}://${IRONIC_EXTERNAL_IP}:6385"
    export IRONIC_EXTERNAL_HTTP_URL="http://${IRONIC_EXTERNAL_IP}:${HTTP_PORT}"
    export IRONIC_INSPECTOR_CALLBACK_ENDPOINT_OVERRIDE="https://${IRONIC_EXTERNAL_IP}:5050"
fi

if [ -f /etc/ironic/ironic.conf ]; then
    # Make a copy of the original supposed empty configuration file
    cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig
fi

# oslo.config also supports Config Opts From Environment, log them
echo '# Options set from Environment variables' | tee /etc/ironic/ironic.extra
env | grep "^OS_" | tee -a /etc/ironic/ironic.extra

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

HTPASSWD_FILE=/etc/ironic/htpasswd
export IRONIC_HTPASSWD=${IRONIC_HTPASSWD:-${HTTP_BASIC_HTPASSWD:-}}
# The user can provide HTTP_BASIC_HTPASSWD and HTTP_BASIC_HTPASSWD_RPC. If
# - we are running conductor and HTTP_BASIC_HTPASSWD is set,
#   use HTTP_BASIC_HTPASSWD for RPC.
export JSON_RPC_AUTH_STRATEGY="noauth"
if [ -n "${IRONIC_HTPASSWD}" ]; then
    if [ "${IRONIC_DEPLOYMENT}" == "Conductor" ]; then
        export JSON_RPC_AUTH_STRATEGY="http_basic"
        printf "%s\n" "${IRONIC_HTPASSWD}" >"${HTPASSWD_FILE}-rpc"
    else
        printf "%s\n" "${IRONIC_HTPASSWD}" >"${HTPASSWD_FILE}"
    fi
fi

# The original ironic.conf is empty, and can be found in ironic.conf_orig
render_j2_config /etc/ironic/ironic.conf.j2 /etc/ironic/ironic.conf

# Configure auth for clients
configure_client_basic_auth() {
    local auth_config_file="/auth/$1/auth-config"
    if [ -f ${auth_config_file} ]; then
        # Merge configurations in the "auth" directory into the default ironic configuration file because there is no way to choose the configuration file 
        # when running the api as a WSGI app.
        crudini --merge "/etc/ironic/ironic.conf" < ${auth_config_file} 
    fi
}

configure_client_basic_auth ironic-inspector
configure_client_basic_auth ironic-rpc
