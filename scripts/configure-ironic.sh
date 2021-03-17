#!/usr/bin/bash

export IRONIC_CERT_FILE=/certs/ironic/tls.crt
export IRONIC_KEY_FILE=/certs/ironic/tls.key
export IRONIC_CACERT_FILE=/certs/ca/ironic/tls.crt
export IRONIC_INSECURE=${IRONIC_INSECURE:-false}

export IRONIC_INSPECTOR_CERT_FILE=/certs/ironic-inspector/tls.crt
export IRONIC_INSPECTOR_CACERT_FILE=/certs/ca/ironic-inspector/tls.crt
export IRONIC_INSPECTOR_INSECURE=${IRONIC_INSPECTOR_INSECURE:-$IRONIC_INSECURE}
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

export HTTP_PORT=${HTTP_PORT:-"80"}
export MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
# TODO(dtantsur): remove the explicit default once we get
# https://review.opendev.org/761185 in the repositories
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMPROC=$(( NUMPROC <= 4 ? NUMPROC : 4 ))
export NUMWORKERS=${NUMWORKERS:-$NUMPROC}
export LISTEN_ALL_INTERFACES="${LISTEN_ALL_INTERFACES:-"true"}"
export IRONIC_DEPLOYMENT="${IRONIC_DEPLOYMENT:-"Combined"}"

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
# - we are running combined and HTTP_BASIC_HTPASSWD is set, i.e. API is
#   authenticated. We want to authenticate RPC by default, but the user might
#   override. Then try to infere the authentication strategy and credentials
#   from /auth/ironic-rpc/auth-config. If not present, then generate a username
#   and password, create the config file the htpasswd content
export JSON_RPC_AUTH_STRATEGY="noauth"
if [ -n "${HTTP_BASIC_HTPASSWD}" ]; then
    if [ "${IRONIC_DEPLOYMENT}" == "Conductor" ]; then
        export JSON_RPC_AUTH_STRATEGY="http_basic"
        printf "%s\n" "${HTTP_BASIC_HTPASSWD}" >"${HTPASSWD_FILE}-rpc"
    else
        printf "%s\n" "${HTTP_BASIC_HTPASSWD}" >"${HTPASSWD_FILE}"
    fi
fi


# When running both API and Conductor in the same container, we'll try to get the credentials
# from /auth/ironic-rpc/auth-config if present, or generate it
if [ "${IRONIC_DEPLOYMENT}" == "Combined" ]; then
    # We try to read the credentials from the config file as it is probably mounted read-only,
    # We cannot modify it. If it is not set to basic, then do not authenticate the RPC. This is
    # to ensure that the setup will work if the user gives a specific config for rpc set to no_auth
    if [ -f "/auth/ironic-rpc/auth-config" ]; then
        IRONIC_RPC_TMP_TYPE="$(crudini --get /auth/ironic-rpc/auth-config json_rpc auth_type)" || exit 1
        if [ "${IRONIC_RPC_TMP_TYPE}" == "http_basic" ]; then
            IRONIC_RPC_TMP_USERNAME="$(crudini --get /auth/ironic-rpc/auth-config json_rpc username)" || exit 1
            IRONIC_RPC_TMP_PASSWORD="$(crudini --get /auth/ironic-rpc/auth-config json_rpc password)" || exit 1
        else
            export JSON_RPC_AUTH_STRATEGY="noauth"
        fi
    # We do not have an auth config file, so we generate one
    else
        IRONIC_RPC_TMP_USERNAME="rpc-user"
        IRONIC_RPC_TMP_PASSWORD="$(tr -dc 'a-zA-Z0-9' < /dev/urandom | fold -w 12 | head -n 1)"
        mkdir -p "/auth/ironic-rpc"
        cat << EOF > "/auth/ironic-rpc/auth-config"
[json_rpc]
auth_type=http_basic
username=${IRONIC_RPC_TMP_USERNAME}
password=${IRONIC_RPC_TMP_PASSWORD}
http_basic_username=${IRONIC_RPC_TMP_USERNAME}
http_basic_password=${IRONIC_RPC_TMP_PASSWORD}
EOF
    fi

    # Populate HTTP_BASIC_HTPASSWD_RPC
    if [ -n "${IRONIC_RPC_TMP_USERNAME:-}" ]; then
        htpasswd -n -b -B "${IRONIC_RPC_TMP_USERNAME}" "${IRONIC_RPC_TMP_PASSWORD}" >"${HTPASSWD_FILE}-rpc"
    fi
fi

# The original ironic.conf is empty, and can be found in ironic.conf_orig
render_j2_config /etc/ironic/ironic.conf.j2 /etc/ironic/ironic.conf

# Configure auth for clients
IRONIC_CONFIG_OPTIONS="--config-file /etc/ironic/ironic.conf"

configure_client_basic_auth() {
    local auth_config_file="/auth/$1/auth-config"
    if [ -f ${auth_config_file} ]; then
        IRONIC_CONFIG_OPTIONS+=" --config-file ${auth_config_file}"
    fi
}

configure_client_basic_auth ironic-inspector
configure_client_basic_auth ironic-rpc
