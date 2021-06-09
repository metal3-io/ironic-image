#!/usr/bin/bash

CONFIG=/etc/ironic-inspector/ironic-inspector.conf

export IRONIC_INSPECTOR_ENABLE_DISCOVERY=${IRONIC_INSPECTOR_ENABLE_DISCOVERY:-false}

export IRONIC_CERT_FILE=/certs/ironic/tls.crt
export IRONIC_CACERT_FILE=/certs/ca/ironic/tls.crt
export IRONIC_INSECURE=${IRONIC_INSECURE:-false}

export IRONIC_INSPECTOR_CACERT_FILE=/certs/ca/ironic-inspector/tls.crt
export IRONIC_INSPECTOR_CERT_FILE=/certs/ironic-inspector/tls.crt
export IRONIC_INSPECTOR_KEY_FILE=/certs/ironic-inspector/tls.key

if [ -f "$IRONIC_INSPECTOR_CERT_FILE" ] && [ ! -f "$IRONIC_INSPECTOR_KEY_FILE" ] ; then
    echo "Missing TLS Certificate key file /certs/ironic-inspector/tls.key"
    exit 1
fi
if [ ! -f "$IRONIC_INSPECTOR_CERT_FILE" ] && [ -f "$IRONIC_INSPECTOR_KEY_FILE" ] ; then
    echo "Missing TLS Certificate file /certs/ironic-inspector/tls.crt"
    exit 1
fi

. /bin/ironic-common.sh

wait_for_interface_or_ip

if [ -f "$IRONIC_INSPECTOR_CERT_FILE" ]; then
    export IRONIC_INSPECTOR_TLS_SETUP="true"
    export IRONIC_INSPECTOR_BASE_URL="https://${IRONIC_URL_HOST}:5050"
    if [ ! -f "${IRONIC_INSPECTOR_CACERT_FILE}"]; then
        cp "${IRONIC_INSPECTOR_CERT_FILE}" "${IRONIC_INSPECTOR_CACERT_FILE}"
    fi
else
    export IRONIC_INSPECTOR_TLS_SETUP="false"
    export IRONIC_INSPECTOR_BASE_URL="http://${IRONIC_URL_HOST}:5050"
fi

if [ -f "$IRONIC_CERT_FILE" ] || [ -f "$IRONIC_CACERT_FILE" ]; then
    export IRONIC_TLS_SETUP="true"
    export IRONIC_BASE_URL="https://${IRONIC_URL_HOST}:6385"
    if [ ! -f "${IRONIC_CACERT_FILE}"]; then
        cp "${IRONIC_CERT_FILE}" "${IRONIC_CACERT_FILE}"
    fi
else
    export IRONIC_TLS_SETUP="false"
    export IRONIC_BASE_URL="http://${IRONIC_URL_HOST}:6385"
fi


function build_j2_config() {
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < $CONFIG.j2
}

# Merge with the original configuration file from the package.
build_j2_config | crudini --merge /etc/ironic-inspector/ironic-inspector.conf

# Configure HTTP basic auth for API server
HTPASSWD_FILE=/etc/ironic-inspector/htpasswd
if [ -n "${HTTP_BASIC_HTPASSWD}" ]; then
    printf "%s\n" "${HTTP_BASIC_HTPASSWD}" >"${HTPASSWD_FILE}"
    crudini --set $CONFIG DEFAULT auth_strategy http_basic
    crudini --set $CONFIG DEFAULT http_basic_auth_user_file "${HTPASSWD_FILE}"
fi

# Configure auth for ironic client
CONFIG_OPTIONS="--config-file /etc/ironic-inspector/inspector-dist.conf --config-file ${CONFIG}"
auth_config_file="/auth/ironic/auth-config"
if [ -f ${auth_config_file} ]; then
    CONFIG_OPTIONS+=" --config-file ${auth_config_file}"
fi

ironic-inspector-dbsync --config-file /etc/ironic-inspector/ironic-inspector.conf upgrade

exec /usr/bin/ironic-inspector $CONFIG_OPTIONS
