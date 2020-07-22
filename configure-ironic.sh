#!/usr/bin/bash

. /bin/ironic-common.sh

# Accepted values noauth and http_basic
IRONIC_AUTH_STRATEGY=${IRONIC_AUTH_STRATEGU:-"noauth"}
IRONIC_HTTP_BASIC_USERNAME=${IRONIC_HTTP_BASIC_USERNAME:-""}
IRONIC_HTTP_BASIC_PASSWORD=${IRONIC_HTTP_BASIC_PASSWORD:-""}

HTTP_PORT=${HTTP_PORT:-"80"}
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))

# Whether to enable fast_track provisioning or not
IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

# Whether cleaning disks before and after deployment
IRONIC_AUTOMATED_CLEAN=${IRONIC_AUTOMATED_CLEAN:-true}

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
bootloader = http://${IRONIC_URL_HOST}:${HTTP_PORT}/uefi_esp.img
automated_clean = ${IRONIC_AUTOMATED_CLEAN}

[database]
connection = mysql+pymysql://ironic:${MARIADB_PASSWORD}@localhost/ironic?charset=utf8

[deploy]
http_url = http://${IRONIC_URL_HOST}:${HTTP_PORT}
fast_track = ${IRONIC_FAST_TRACK}

[inspector]
endpoint_override = http://${IRONIC_URL_HOST}:5050
power_off = ${INSPECTOR_POWER_OFF}
# NOTE(dtantsur): keep inspection arguments synchronized with inspector.ipxe
extra_kernel_params = console=ttyS0 ipa-inspector-collectors=default,extra-hardware,logs ipa-inspection-dhcp-all-interfaces=1 ipa-collect-lldp=1 ${INSPECTOR_EXTRA_ARGS}

[service_catalog]
endpoint_override = http://${IRONIC_URL_HOST}:6385
EOF

# oslo.config also supports Config Opts From Environment, log them
echo '# Options set from Environment variables' | tee /etc/ironic/ironic.extra
env | grep "^OS_" | tee -a /etc/ironic/ironic.extra

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter

if [ "$IRONIC_AUTH_STRATEGY" == "http_basic" ]; then

	if [[ "$IRONIC_HTTP_BASIC_USERNAME" == "" || "$IRONIC_HTTP_BASIC_PASSWORD" == "" ]]; then
		echo "Please set IRONIC_HTTP_BASIC_USERNAME and IRONIC_HTTP_BASIC_PASSWORD"
		exit 1
	fi

	crudini --set /etc/ironic/ironic.conf DEFAULT auth_strategy http_basic
	crudini --set /etc/ironic/ironic.conf DEFAULT http_basic_auth_user_file /shared/htpasswd-ironic
	crudini --set /etc/ironic/ironic.conf json_rpc auth_strategy http_basic
	crudini --set /etc/ironic/ironic.conf json_rpc http_basic_auth_user_file /shared/htpasswd-ironic
	crudini --set /etc/ironic/ironic.conf json_rpc username $IRONIC_HTTP_BASIC_USERNAME
	crudini --set /etc/ironic/ironic.conf json_rpc password $IRONIC_HTTP_BASIC_PASSWORD

	## NOTE(iurygregory): reusing the ironic credentials so we don't end up with wrong client credentials
	htpasswd -nbB $IRONIC_HTTP_BASIC_USERNAME $IRONIC_HTTP_BASIC_PASSWORD > /shared/htpasswd-ironic
fi
