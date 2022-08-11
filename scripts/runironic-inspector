#!/usr/bin/bash

set -euxo pipefail

CONFIG=/etc/ironic-inspector/ironic-inspector.conf

export IRONIC_INSPECTOR_ENABLE_DISCOVERY=${IRONIC_INSPECTOR_ENABLE_DISCOVERY:-false}

export INSPECTOR_REVERSE_PROXY_SETUP=${INSPECTOR_REVERSE_PROXY_SETUP:-"false"}

. /bin/tls-common.sh

. /bin/ironic-common.sh

wait_for_interface_or_ip

IRONIC_INSPECTOR_PORT=${IRONIC_INSPECTOR_ACCESS_PORT}
if [ "$IRONIC_INSPECTOR_TLS_SETUP" = "true" ]; then
    if [[ "${INSPECTOR_REVERSE_PROXY_SETUP}" == "true" && "${IRONIC_INSPECTOR_PRIVATE_PORT}" != "unix" ]]; then
        IRONIC_INSPECTOR_PORT=$IRONIC_INSPECTOR_PRIVATE_PORT
    fi
else
    export INSPECTOR_REVERSE_PROXY_SETUP="false" # If TLS is not used, we have no reason to use the reverse proxy
fi
export IRONIC_INSPECTOR_BASE_URL="${IRONIC_INSPECTOR_SCHEME}://${IRONIC_URL_HOST}:${IRONIC_INSPECTOR_PORT}"

export IRONIC_BASE_URL="${IRONIC_SCHEME}://${IRONIC_URL_HOST}:${IRONIC_ACCESS_PORT}"

export INSPECTOR_HTPASSWD=${INSPECTOR_HTPASSWD:-${HTTP_BASIC_HTPASSWD:-}}

function build_j2_config() {
  CONFIG_FILE=$1
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < $CONFIG_FILE.j2
}

# Merge with the original configuration file from the package.
build_j2_config $CONFIG | crudini --merge $CONFIG


# Configure HTTP basic auth for API server
HTPASSWD_FILE=/etc/ironic-inspector/htpasswd
if [ -n "${INSPECTOR_HTPASSWD}" ]; then
    printf "%s\n" "${INSPECTOR_HTPASSWD}" >"${HTPASSWD_FILE}"
    if [[ $INSPECTOR_REVERSE_PROXY_SETUP == "false" ]]; then
      crudini --set $CONFIG DEFAULT auth_strategy http_basic
      crudini --set $CONFIG DEFAULT http_basic_auth_user_file "${HTPASSWD_FILE}"
    fi
fi

# Configure auth for ironic client
CONFIG_OPTIONS="--config-file ${CONFIG}"
auth_config_file="/auth/ironic/auth-config"
if [ -f ${auth_config_file} ]; then
    CONFIG_OPTIONS+=" --config-file ${auth_config_file}"
fi

ironic-inspector-dbsync --config-file /etc/ironic-inspector/ironic-inspector.conf upgrade

if [[ "$INSPECTOR_REVERSE_PROXY_SETUP" == "false" && "${RESTART_CONTAINER_CERTIFICATE_UPDATED}" == "true" ]]; then
    inotifywait -m -e delete_self "${IRONIC_INSPECTOR_CERT_FILE}" | while read file event; do
    kill $(pgrep ironic)
    done &
fi

exec /usr/bin/ironic-inspector $CONFIG_OPTIONS
