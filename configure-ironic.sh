#!/usr/bin/bash

. /bin/ironic-common.sh

USE_HTTP_BASIC=${USE_HTTP_BASIC:-false}
IRONIC_HTTP_BASIC_USERNAME=${IRONIC_HTTP_BASIC_USERNAME:-"change_me"}
IRONIC_HTTP_BASIC_PASSWORD=${IRONIC_HTTP_BASIC_PASSWORD:-"change_me"}

HTTP_PORT=${HTTP_PORT:-"80"}
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))

# Whether to enable fast_track provisioning or not
IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

# Whether cleaning disks before and after deployment
IRONIC_AUTOMATED_CLEAN=${IRONIC_AUTOMATED_CLEAN:-true}

wait_for_interface_or_ip

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

crudini --merge /etc/ironic/ironic.conf <<EOF
[DEFAULT]
my_ip = $IRONIC_IP

[api]
host_ip = ::
api_workers = $NUMWORKERS

[conductor]
bootloader = http://${IRONIC_URL_HOST}:${HTTP_PORT}/uefi_esp.img
automated_clean = ${IRONIC_AUTOMATED_CLEAN}

[database]
connection = mysql+pymysql://ironic:${MARIADB_PASSWORD}@localhost/ironic?charset=utf8

[deploy]
http_url = http://${IRONIC_URL_HOST}:${HTTP_PORT}
fast_track = ${IRONIC_FAST_TRACK}

[inspector]
endpoint_override = http://${IRONIC_URL_HOST}:5050

[service_catalog]
endpoint_override = http://${IRONIC_URL_HOST}:6385
EOF

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

if [ "$USE_HTTP_BASIC" = "true" ]; then

	crudini --set /etc/ironic/ironic.conf DEFAULT auth_strategy http_basic
	crudini --set /etc/ironic/ironic.conf DEFAULT http_basic_auth_user_file /shared/htpasswd-ironic
	crudini --set /etc/ironic/ironic.conf json_rpc auth_strategy http_basic
	crudini --set /etc/ironic/ironic.conf json_rpc http_basic_auth_user_file /shared/htpasswd-ironic
	crudini --set /etc/ironic/ironic.conf json_rpc http_basic_username $IRONIC_HTTP_BASIC_USERNAME
	crudini --set /etc/ironic/ironic.conf json_rpc http_basic_password $IRONIC_HTTP_BASIC_PASSWORD

	## NOTE(iurygregory): reusing the ironic credentials so we don't end up with wrong client credentials
	htpasswd -nbB $IRONIC_HTTP_BASIC_USERNAME $IRONIC_HTTP_BASIC_PASSWORD > /shared/htpasswd-ironic
fi
