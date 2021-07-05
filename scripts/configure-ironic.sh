#!/usr/bin/bash

export IRONIC_CERT_FILE=/certs/ironic/tls.crt
export IRONIC_KEY_FILE=/certs/ironic/tls.key
export IRONIC_CACERT_FILE=/certs/ca/ironic/tls.crt
export IRONIC_INSECURE=${IRONIC_INSECURE:-false}

export IRONIC_INSPECTOR_CERT_FILE=/certs/ironic-inspector/tls.crt
export IRONIC_INSPECTOR_CACERT_FILE=/certs/ca/ironic-inspector/tls.crt
export IRONIC_INSPECTOR_INSECURE=${IRONIC_INSPECTOR_INSECURE:-$IRONIC_INSECURE}
export RESTART_CONTAINER_CERTIFICATE_UPDATED=${RESTART_CONTAINER_CERTIFICATE_UPDATED:-"false"}

# Define the VLAN interfaces to be included in introspection report, e.g.
#   all - all VLANs on all interfaces using LLDP information
#   <interface> - all VLANs on a particular interface using LLDP information
#   <interface.vlan> - a particular VLAN on an interface, not relying on LLDP
export IRONIC_INSPECTOR_VLAN_INTERFACES=${IRONIC_INSPECTOR_VLAN_INTERFACES:-all}

export MARIADB_CACERT_FILE=/certs/ca/mariadb/tls.crt

mkdir -p /certs/ironic
mkdir -p /certs/ironic-inspector
mkdir -p /certs/ca/ironic
mkdir -p /certs/ca/ironic-inspector

if [ -f "$IRONIC_CERT_FILE" ] && [ ! -f "$IRONIC_KEY_FILE" ] ; then
    echo "Missing TLS Certificate key file /certs/ironic/key"
    exit 1
fi
if [ ! -f "$IRONIC_CERT_FILE" ] && [ -f "$IRONIC_KEY_FILE" ] ; then
    echo "Missing TLS Certificate file /certs/ironic/crt"
    exit 1
fi

. /bin/ironic-common.sh

export MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
# TODO(dtantsur): remove the explicit default once we get
# https://review.opendev.org/761185 in the repositories
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMPROC=$(( NUMPROC <= 4 ? NUMPROC : 4 ))
export NUMWORKERS=${NUMWORKERS:-$NUMPROC}
export LISTEN_ALL_INTERFACES="${LISTEN_ALL_INTERFACES:-"true"}"

# Whether to enable fast_track provisioning or not
export IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

# Whether cleaning disks before and after deployment
export IRONIC_AUTOMATED_CLEAN=${IRONIC_AUTOMATED_CLEAN:-true}

# Wheter to enable the sensor data collection
export SEND_SENSOR_DATA=${SEND_SENSOR_DATA:-false}

wait_for_interface_or_ip

if [ -f "$IRONIC_CERT_FILE" ]; then
    export IRONIC_TLS_SETUP="true"
    export IRONIC_BASE_URL="https://${IRONIC_URL_HOST}:6385"
    if [ ! -f "$IRONIC_CACERT_FILE" ]; then
        cp "$IRONIC_CERT_FILE" "$IRONIC_CACERT_FILE"
    fi
else
    export IRONIC_TLS_SETUP="false"
    export IRONIC_BASE_URL="http://${IRONIC_URL_HOST}:6385"
fi

if [ -f "$IRONIC_INSPECTOR_CERT_FILE" ] || [ -f "$IRONIC_INSPECTOR_CACERT_FILE" ]; then
    export IRONIC_INSPECTOR_TLS_SETUP="true"
    export IRONIC_INSPECTOR_BASE_URL="https://${IRONIC_URL_HOST}:5050"
    if [ ! -f "$IRONIC_INSPECTOR_CACERT_FILE" ]; then
        cp "$IRONIC_INSPECTOR_CERT_FILE" "$IRONIC_INSPECTOR_CACERT_FILE"
    fi
else
    export IRONIC_INSPECTOR_TLS_SETUP="false"
    export IRONIC_INSPECTOR_BASE_URL="http://${IRONIC_URL_HOST}:5050"
fi

if  [ -f "$MARIADB_CACERT_FILE" ]; then
    export MARIADB_TLS_ENABLED="true"
else
    export MARIADB_TLS_ENABLED="false"
fi

if [ ! -z "${IRONIC_EXTERNAL_IP}" ]; then
	if [ "${IRONIC_INSPECTOR_TLS_SETUP}" == "true" ]; then
		export IRONIC_EXTERNAL_CALLBACK_URL="https://${IRONIC_EXTERNAL_IP}:6385"
	else
		export IRONIC_EXTERNAL_CALLBACK_URL="http://${IRONIC_EXTERNAL_IP}:6385"
	fi
	export IRONIC_EXTERNAL_HTTP_URL="http://${IRONIC_EXTERNAL_IP}:6180"
fi

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

# oslo.config also supports Config Opts From Environment, log them
echo '# Options set from Environment variables' | tee /etc/ironic/ironic.extra
env | grep "^OS_" | tee -a /etc/ironic/ironic.extra

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

HTPASSWD_FILE=/etc/ironic/htpasswd
# The user can provide HTTP_BASIC_HTPASSWD and HTTP_BASIC_HTPASSWD_RPC. If
# - we are running conductor and HTTP_BASIC_HTPASSWD is set,
#   use HTTP_BASIC_HTPASSWD for RPC.
export JSON_RPC_AUTH_STRATEGY="noauth"
if [ -n "${HTTP_BASIC_HTPASSWD}" ]; then
    if [ "${IRONIC_DEPLOYMENT}" == "Conductor" ]; then
        export JSON_RPC_AUTH_STRATEGY="http_basic"
        printf "%s\n" "${HTTP_BASIC_HTPASSWD}" >"${HTPASSWD_FILE}-rpc"
    else
        printf "%s\n" "${HTTP_BASIC_HTPASSWD}" >"${HTPASSWD_FILE}"
    fi
fi

. /bin/coreos-ipa-common.sh

# The original ironic.conf is empty, and can be found in ironic.conf_orig
render_j2_config /etc/ironic/ironic.conf.j2 /etc/ironic/ironic.conf

# Configure auth for clients
configure_client_basic_auth() {
    local auth_config_file="/auth/$1/auth-config"
    if [ -f ${auth_config_file} ]; then
        # Merge configurations in the "auth" directory into the default ironic
        # configuration file because there is no way to choose the configuration
        # file when running the api as a WSGI app.
        crudini --merge "/etc/ironic/ironic.conf" < ${auth_config_file} 
    fi
}

configure_client_basic_auth ironic-inspector
configure_client_basic_auth ironic-rpc
