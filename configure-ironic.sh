#!/usr/bin/bash

# Get environment settings and update ironic.conf
PROVISIONING_INTERFACE=${PROVISIONING_INTERFACE:-"provisioning"}
IRONIC_IP=$(ip -4 address show dev "$PROVISIONING_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
until [ ! -z "${IRONIC_IP}" ]; do
  echo "Waiting for ${PROVISIONING_INTERFACE} interface to be configured"
  sleep 1
  IRONIC_IP=$(ip -4 address show dev "$PROVISIONING_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
done
HTTP_PORT=${HTTP_PORT:-"80"}
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))

# Whether to enable fast_track provisioning or not
IRONIC_FAST_TRACK=${IRONIC_FAST_TRACK:-true}

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

crudini --merge /etc/ironic/ironic.conf <<EOF
[DEFAULT]
my_ip = $IRONIC_IP

[api]
api_workers = $NUMWORKERS

[conductor]
api_url = http://${IRONIC_IP}:6385

[database]
connection = mysql+pymysql://ironic:${MARIADB_PASSWORD}@localhost/ironic?charset=utf8

[deploy]
http_url = http://${IRONIC_IP}:${HTTP_PORT}
fast_track = ${IRONIC_FAST_TRACK}

[inspector]
endpoint_override = http://${IRONIC_IP}:5050

[mdns]
interfaces = $IRONIC_IP
EOF

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter
