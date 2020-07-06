#!/usr/bin/bash

. /bin/ironic-common.sh

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
host = $IRONIC_IP

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

EOF

if [ ! -z "$CLIENT_CERT_FILE" ] || [ ! -z "$CLIENT_KEY_FILE" ] || [ ! -z "$CACERT_FILE" ] || [ ! -z "$INSECURE" ]; then
    crudini --merge /etc/ironic/ironic.conf <<EOF
[inspector]
endpoint_override = https://${IRONIC_URL_HOST}:5050
$([ ! -z "$CLIENT_CERT_FILE" ] && echo "certfile = $CLIENT_CERT_FILE")
$([ ! -z "$CLIENT_KEY_FILE" ] && echo "keyfile = $CLIENT_KEY_FILE")
$([ ! -z "$CACERT_FILE" ] && echo "cafile = $CACERT_FILE")
$([ ! -z "$INSECURE" ] && echo "insecure = $INSECURE" || echo "insecure = false")

# TODO(dtantsur): ipa-api-url should be populated by ironic itself, but it's
# not, so working around here.
# NOTE(dtantsur): keep inspection arguments synchronized with inspector.ipxe
extra_kernel_params = ipa-insecure=True ipa-inspector-collectors=default,extra-hardware,logs ipa-inspection-dhcp-all-interfaces=1 ipa-collect-lldp=1 ipa-api-url=https://${IRONIC_URL_HOST}:6385

[service_catalog]
endpoint_override = https://${IRONIC_URL_HOST}:6385
$([ ! -z "$CLIENT_CERT_FILE" ] && echo "certfile = $CLIENT_CERT_FILE")
$([ ! -z "$CLIENT_KEY_FILE" ] && echo "keyfile = $CLIENT_KEY_FILE")
$([ ! -z "$CACERT_FILE" ] && echo "cafile = $CACERT_FILE")
$([ ! -z "$INSECURE" ] && echo "insecure = $INSECURE" || echo "insecure = false")
EOF
else
    crudini --merge /etc/ironic/ironic.conf <<EOF
[inspector]
endpoint_override = http://${IRONIC_URL_HOST}:5050

# TODO(dtantsur): ipa-api-url should be populated by ironic itself, but it's
# not, so working around here.
# NOTE(dtantsur): keep inspection arguments synchronized with inspector.ipxe
extra_kernel_params = ipa-inspector-collectors=default,extra-hardware,logs ipa-inspection-dhcp-all-interfaces=1 ipa-collect-lldp=1 ipa-api-url=http://${IRONIC_URL_HOST}:6385

[service_catalog]
endpoint_override = http://${IRONIC_URL_HOST}:6385
EOF
fi

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter
