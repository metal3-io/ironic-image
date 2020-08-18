#!/usr/bin/bash

. /bin/ironic-common.sh

HTTP_PORT=${HTTP_PORT:-"80"}
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))

# Whether to enable fast_track provisioning or not
IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

wait_for_interface_or_ip

if [[ $IRONIC_FAST_TRACK == true ]]; then
    INSPECTOR_POWER_OFF=false
    # TODO(dtantsur): ipa-api-url should be populated by ironic itself, but
    # it's not yet, so working around here.
    INSPECTOR_EXTRA_ARGS=" ipa-api-url=http://${IRONIC_URL_HOST}:6385"
else
    INSPECTOR_POWER_OFF=true
    INSPECTOR_EXTRA_ARGS=""
fi

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

crudini --merge /etc/ironic/ironic.conf <<EOF
[DEFAULT]
my_ip = $IRONIC_IP

[api]
host_ip = ::
api_workers = $NUMWORKERS

[conductor]

[database]
connection = mysql+pymysql://ironic:${MARIADB_PASSWORD}@localhost/ironic?charset=utf8

[deploy]
http_url = http://${IRONIC_URL_HOST}:${HTTP_PORT}
fast_track = ${IRONIC_FAST_TRACK}

[inspector]
endpoint_override = http://${IRONIC_URL_HOST}:5050
power_off = ${INSPECTOR_POWER_OFF}
# NOTE(dtantsur): keep inspection arguments synchronized with inspector.ipxe
extra_kernel_params = ipa-inspection-collectors=default,extra-hardware,logs ipa-inspection-dhcp-all-interfaces=1 ipa-collect-lldp=1 ${INSPECTOR_EXTRA_ARGS}

[mdns]
interfaces = $IRONIC_IP

[service_catalog]
endpoint_override = http://${IRONIC_URL_HOST}:6385
EOF

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

HTPASSWD_FILE=/etc/ironic/htpasswd
if [ -n "${HTTP_BASIC_HTPASSWD}" ]; then
    printf "%s\n" "${HTTP_BASIC_HTPASSWD}" >"${HTPASSWD_FILE}"
fi
set_http_basic_server_auth_strategy() {
    local section=${1:-DEFAULT}
    crudini --set /etc/ironic/ironic.conf ${section} auth_strategy http_basic
    crudini --set /etc/ironic/ironic.conf ${section} http_basic_auth_user_file "${HTPASSWD_FILE}"
}

# Configure HTTP basic auth for ironic-api server
if [ -f "${HTPASSWD_FILE}" ]; then
    set_http_basic_server_auth_strategy
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
