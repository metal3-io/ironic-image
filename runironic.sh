#!/usr/bin/bash

# Get environment settings and update ironic.conf
PROVISIONING_INTERFACE=${PROVISIONING_INTERFACE:-"provisioning"}
IRONIC_IP=$(ip -4 address show dev "$PROVISIONING_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
HTTP_PORT=${HTTP_PORT:-"80"}
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
NUMPROC=$(cat /proc/cpuinfo  | grep "^processor" | wc -l)
NUMWORKERS=$(( NUMPROC < 12 ? NUMPROC : 12 ))


# Allow access to Ironic
if ! iptables -C INPUT -i "$PROVISIONING_INTERFACE" -p tcp -m tcp --dport 6385 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i "$PROVISIONING_INTERFACE" -p tcp -m tcp --dport 6385 -j ACCEPT
fi

# Allow access to mDNS
if ! iptables -C INPUT -i $PROVISIONING_INTERFACE -p udp --dport 5353 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i $PROVISIONING_INTERFACE -p udp --dport 5353 -j ACCEPT
fi
if ! iptables -C OUTPUT -p udp --dport 5353 -j ACCEPT > /dev/null 2>&1; then
    iptables -I OUTPUT -p udp --dport 5353 -j ACCEPT
fi

cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig

crudini --set /etc/ironic/ironic.conf DEFAULT auth_strategy noauth
crudini --set /etc/ironic/ironic.conf DEFAULT my_ip "$IRONIC_IP"
crudini --set /etc/ironic/ironic.conf DEFAULT debug true
crudini --set /etc/ironic/ironic.conf DEFAULT default_network_interface noop
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_boot_interfaces pxe,ipxe,fake
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_power_interfaces ipmitool,idrac,fake
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_management_interfaces ipmitool,idrac,fake
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_hardware_types ipmi,idrac,fake-hardware
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_vendor_interfaces ipmitool,no-vendor,idrac,fake
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_deploy_interfaces direct,fake
crudini --set /etc/ironic/ironic.conf DEFAULT default_boot_interface ipxe
crudini --set /etc/ironic/ironic.conf DEFAULT default_deploy_interface direct
crudini --set /etc/ironic/ironic.conf DEFAULT enabled_inspect_interfaces inspector,idrac,fake
crudini --set /etc/ironic/ironic.conf DEFAULT default_inspect_interface inspector
crudini --set /etc/ironic/ironic.conf DEFAULT rpc_transport json-rpc
crudini --set /etc/ironic/ironic.conf conductor enable_mdns True
crudini --set /etc/ironic/ironic.conf conductor send_sensor_data true
crudini --set /etc/ironic/ironic.conf oslo_messaging_notifications driver prometheus_exporter
crudini --set /etc/ironic/ironic.conf oslo_messaging_notifications transport_url fake://
crudini --set /etc/ironic/ironic.conf oslo_messaging_notifications location /tmp/ironic_prometheus_exporter
crudini --set /etc/ironic/ironic.conf dhcp dhcp_provider none
crudini --set /etc/ironic/ironic.conf conductor automated_clean true
crudini --set /etc/ironic/ironic.conf conductor api_url http://${IRONIC_IP}:6385
crudini --set /etc/ironic/ironic.conf database connection mysql+pymysql://ironic:${MARIADB_PASSWORD}@localhost/ironic?charset=utf8
crudini --set /etc/ironic/ironic.conf deploy http_url http://${IRONIC_IP}:${HTTP_PORT}
crudini --set /etc/ironic/ironic.conf deploy http_root /shared/html/
crudini --set /etc/ironic/ironic.conf deploy default_boot_option local
crudini --set /etc/ironic/ironic.conf deploy erase_devices_priority 0
crudini --set /etc/ironic/ironic.conf deploy erase_devices_metadata_priority 10
crudini --set /etc/ironic/ironic.conf inspector endpoint_override http://${IRONIC_IP}:5050
crudini --set /etc/ironic/ironic.conf pxe ipxe_enabled true
crudini --set /etc/ironic/ironic.conf pxe tftp_root /shared/tftpboot
crudini --set /etc/ironic/ironic.conf pxe tftp_master_path /shared/tftpboot
crudini --set /etc/ironic/ironic.conf pxe instance_master_path /shared/html/master_images
crudini --set /etc/ironic/ironic.conf pxe images_path /shared/html/tmp
crudini --set /etc/ironic/ironic.conf pxe pxe_config_template \$pybasedir/drivers/modules/ipxe_config.template
crudini --set /etc/ironic/ironic.conf pxe uefi_pxe_config_template \$pybasedir/drivers/modules/ipxe_config.template
crudini --set /etc/ironic/ironic.conf agent deploy_logs_collect always
crudini --set /etc/ironic/ironic.conf agent deploy_logs_local_path /shared/log/ironic/deploy
crudini --set /etc/ironic/ironic.conf api api_workers "$NUMWORKERS"

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

mkdir -p /shared/html

# Remove log files from last deployment
rm -rf /shared/log/ironic

mkdir -p /shared/log/ironic

/usr/bin/ironic-conductor --log-file /shared/log/ironic/ironic-conductor.log &
/usr/bin/ironic-api --log-file  /shared/log/ironic/ironic-api.log &

/bin/runhealthcheck "ironic" &>/dev/null &
/bin/runexporterapp &

sleep infinity

