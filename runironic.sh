#!/usr/bin/bash

# Get environment settings and update ironic.conf
IP=${IP:-"172.22.0.1"}
HTTP_PORT=${HTTP_PORT:-"80"}
INTERFACE=${INTERFACE:-"provisioning"}
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))

# Configuration for hardware types and interfaces
ENABLED_HARDWARE_TYPES=${ENABLED_HARDWARE_TYPES:-"ipmi,idrac,fake-hardware"}
ENABLED_BOOT_INTERFACES=${ENABLED_BOOT_INTERFACES:-"pxe,ipxe,fake"}
DEFAULT_BOOT_INTERFACE=${DEFAULT_BOOT_INTERFACE:-"ipxe"}
ENABLED_DEPLOY_INTERFACES=${ENABLED_DEPLOY_INTERFACES:-"direct,fake"}
DEFAULT_DEPLOY_INTERFACE=${DEFAULT_DEPLOY_INTERFACE:-"direct"}
ENABLED_INSPECT_INTERFACES=${ENABLED_INSPECT_INTERFACES:-"inspector,idrac,fake"}
DEFAULT_INSPECT_INTERFACE=${DEFAULT_INSPECT_INTERFACE:-"inspector"}
ENABLED_MANAGEMENT_INTERFACES=${ENABLED_MANAGEMENT_INTERFACES:-"ipmitool,idrac,fake"}
ENABLED_POWER_INTERFACES=${ENABLED_POWER_INTERFACES:-"ipmitool,idrac,fake"}
ENABLED_VENDOR_INTERFACES=${ENABLED_VENDOR_INTERFACES:-"ipmitool,no-vendor,idrac,fake"}

# Allow access to Ironic
if ! iptables -C INPUT -i $INTERFACE -p tcp -m tcp --dport 6385 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i $INTERFACE -p tcp -m tcp --dport 6385 -j ACCEPT
fi

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

crudini --set /etc/ironic/ironic.conf DEFAULT auth_strategy noauth
crudini --set /etc/ironic/ironic.conf DEFAULT my_ip ${IP}
crudini --set /etc/ironic/ironic.conf DEFAULT debug true 
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_hardware_types ${ENABLED_HARDWARE_TYPES}
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_boot_interfaces ${ENABLED_BOOT_INTERFACES}
crudini --set /etc/ironic/ironic.conf DEFAULT default_boot_interface ${DEFAULT_BOOT_INTERFACE}
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_deploy_interfaces ${ENABLED_DEPLOY_INTERFACES}
crudini --set /etc/ironic/ironic.conf DEFAULT default_deploy_interface ${DEFAULT_DEPLOY_INTERFACE}
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_inspect_interfaces ${ENABLED_INSPECT_INTERFACES}
crudini --set /etc/ironic/ironic.conf DEFAULT default_inspect_interface ${DEFAULT_INSPECT_INTERFACE}
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_power_interfaces ${ENABLED_POWER_INTERFACES}
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_management_interfaces ${ENABLED_MANAGEMENT_INTERFACES}
crudini --set /etc/ironic/ironic.conf DEFAULT default_network_interface noop
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_vendor_interfaces ${ENABLED_VENDOR_INTERFACES}
crudini --set /etc/ironic/ironic.conf DEFAULT rpc_transport json-rpc
crudini --set /etc/ironic/ironic.conf conductor send_sensor_data true
crudini --set /etc/ironic/ironic.conf oslo_messaging_notifications driver prometheus_exporter
crudini --set /etc/ironic/ironic.conf oslo_messaging_notifications transport_url fake://
crudini --set /etc/ironic/ironic.conf oslo_messaging_notifications location /tmp/ironic_prometheus_exporter
crudini --set /etc/ironic/ironic.conf dhcp dhcp_provider none
crudini --set /etc/ironic/ironic.conf conductor automated_clean true
crudini --set /etc/ironic/ironic.conf conductor api_url http://${IP}:6385
crudini --set /etc/ironic/ironic.conf database connection mysql+pymysql://ironic:${MARIADB_PASSWORD}@localhost/ironic?charset=utf8
crudini --set /etc/ironic/ironic.conf deploy http_url http://${IP}:${HTTP_PORT}
crudini --set /etc/ironic/ironic.conf deploy http_root /shared/html/
crudini --set /etc/ironic/ironic.conf deploy default_boot_option local
crudini --set /etc/ironic/ironic.conf deploy erase_devices_priority 0
crudini --set /etc/ironic/ironic.conf deploy erase_devices_metadata_priority 10
crudini --set /etc/ironic/ironic.conf inspector endpoint_override http://${IP}:5050
crudini --set /etc/ironic/ironic.conf pxe ipxe_enabled true
crudini --set /etc/ironic/ironic.conf pxe tftp_root /shared/tftpboot
crudini --set /etc/ironic/ironic.conf pxe tftp_master_path /shared/tftpboot
crudini --set /etc/ironic/ironic.conf pxe instance_master_path /shared/html/master_images
crudini --set /etc/ironic/ironic.conf pxe images_path /shared/html/tmp
crudini --set /etc/ironic/ironic.conf pxe pxe_config_template \$pybasedir/drivers/modules/ipxe_config.template
crudini --set /etc/ironic/ironic.conf pxe uefi_pxe_config_template \$pybasedir/drivers/modules/ipxe_config.template
crudini --set /etc/ironic/ironic.conf agent deploy_logs_collect always
crudini --set /etc/ironic/ironic.conf agent deploy_logs_local_path /shared/log/ironic/deploy
crudini --set /etc/ironic/ironic.conf api api_workers ${NUMWORKERS}

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

mkdir -p /shared/html

# Remove log files from last deployment
rm -rf /shared/log/ironic

mkdir -p /shared/log/ironic

/usr/bin/python2 /usr/bin/ironic-conductor --log-file /shared/log/ironic/ironic-conductor.log &
/usr/bin/python2 /usr/bin/ironic-api --log-file  /shared/log/ironic/ironic-api.log & 

/bin/runhealthcheck "ironic" &>/dev/null &
/bin/runexporterapp &

sleep infinity

