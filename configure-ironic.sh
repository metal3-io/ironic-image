#!/usr/bin/bash

. /bin/ironic-common.sh

export HTTP_PORT=${HTTP_PORT:-"80"}
export MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
export NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
export NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))
export LISTEN_ALL_INTERFACES="${LISTEN_ALL_INTERFACES:-"true"}"
export IRONIC_DEPLOYMENT="${IRONIC_DEPLOYMENT:-"Combined"}"

# Whether to enable fast_track provisioning or not
export IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

# Whether cleaning disks before and after deployment
export IRONIC_AUTOMATED_CLEAN=${IRONIC_AUTOMATED_CLEAN:-true}

wait_for_interface_or_ip

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

function render_j2_config () {
    python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < /etc/ironic/ironic.conf.j2
}

# The original ironic.conf is empty, and can be found in ironic.conf_orig
render_j2_config > /etc/ironic/ironic.conf

# oslo.config also supports Config Opts From Environment, log them
echo '# Options set from Environment variables' | tee /etc/ironic/ironic.extra
env | grep "^OS_" | tee -a /etc/ironic/ironic.extra

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

HTPASSWD_FILE=/etc/ironic/htpasswd
if [ -n "${HTTP_BASIC_HTPASSWD}" ]; then
    printf "%s\n" "${HTTP_BASIC_HTPASSWD}" >"${HTPASSWD_FILE}"
fi

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
