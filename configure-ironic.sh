#!/usr/bin/bash

# Get environment settings and update ironic.conf
PROVISIONING_INTERFACE=${PROVISIONING_INTERFACE:-"provisioning"}
IRONIC_IP=$(ip -4 address show dev "$PROVISIONING_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
HTTP_PORT=${HTTP_PORT:-"80"}
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))

# Configuration for hardware types and interfaces
# ENV var ENABLED_HARDWARE_TYPES overrides hardware types config
# ENV vars ENABLED_<HWIF>_INTERFACES override hardware interfaces config
# ENV vars DEFAULT_<HWIF>_INTERFACE override default hardware interfaces config
HW_TYPES_CONFIG=""
HW_IFS_CONFIG=""
[[ "$ENABLED_HARDWARE_TYPES" != "" ]] && HW_TYPES_CONFIG="enabled_hardware_types=$ENABLED_HARDWARE_TYPES"
HW_IFS=(bios boot console deploy inspect management network power raid rescue storage vendor)
for hw_if in ${HW_IFS[*]}
do
  # Get env var ENABLED_<HWIF>_INTERFACES
  env_name="ENABLED_${hw_if^^}_INTERFACES"
  env_val="${!env_name}"
  [[ "$env_val" != "" ]] && HW_IFS_CONFIG+=$(printf "\nenabled_${hw_if}_interfaces=$env_val")
  # Get env var DEFAULT_<HWIF>_INTERFACE
  env_name="DEFAULT_${hw_if^^}_INTERFACE"
  env_val="${!env_name}"
  [[ "$env_val" != "" ]] && HW_IFS_CONFIG+=$(printf "\ndefault_${hw_if}_interface=$env_val")
done

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

crudini --merge /etc/ironic/ironic.conf <<EOF
[DEFAULT]
my_ip = $IRONIC_IP

$HW_TYPES_CONFIG
$HW_IFS_CONFIG

[api]
api_workers = $NUMWORKERS

[conductor]
api_url = http://${IRONIC_IP}:6385

[database]
connection = mysql+pymysql://ironic:${MARIADB_PASSWORD}@localhost/ironic?charset=utf8

[deploy]
http_url = http://${IRONIC_IP}:${HTTP_PORT}

[inspector]
endpoint_override = http://${IRONIC_IP}:5050
EOF

mkdir -p /shared/html
mkdir -p /shared/ironic_prometheus_exporter
