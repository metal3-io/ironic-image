FROM docker.io/centos:centos7

RUN yum install -y python-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python - current && \
    yum install -y openstack-ironic-api openstack-ironic-conductor crudini iproute dnsmasq httpd qemu-img-ev iscsi-initiator-utils parted gdisk ipxe-bootimgs psmisc sysvinit-tools && \
    yum clean all

RUN mkdir /tftpboot && \
    cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /tftpboot/

RUN mkdir -p /var/lib/ironic && \
    sqlite3 /var/lib/ironic/ironic.db "pragma journal_mode=wal"

RUN cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig && \
    crudini --set /etc/ironic/ironic.conf DEFAULT auth_strategy noauth && \
    crudini --set /etc/ironic/ironic.conf DEFAULT my_ip 172.22.0.1 && \
    crudini --set /etc/ironic/ironic.conf DEFAULT debug true && \
    crudini --set /etc/ironic/ironic.conf DEFAULT default_network_interface noop && \
    crudini --set /etc/ironic/ironic.conf DEFAULT enabled_boot_interfaces pxe,ipxe && \
    crudini --set /etc/ironic/ironic.conf DEFAULT enabled_power_interfaces ipmitool,idrac && \
    crudini --set /etc/ironic/ironic.conf DEFAULT enabled_management_interfaces ipmitool,idrac && \
    crudini --set /etc/ironic/ironic.conf DEFAULT enabled_hardware_types ipmi,idrac && \
    crudini --set /etc/ironic/ironic.conf DEFAULT enabled_vendor_interfaces ipmitool,no-vendor,idrac && \
    crudini --set /etc/ironic/ironic.conf DEFAULT default_boot_interface ipxe && \
    crudini --set /etc/ironic/ironic.conf DEFAULT default_deploy_interface direct && \
    crudini --set /etc/ironic/ironic.conf DEFAULT enabled_inspect_interfaces inspector,idrac && \
    crudini --set /etc/ironic/ironic.conf DEFAULT default_inspect_interface inspector && \
    crudini --set /etc/ironic/ironic.conf DEFAULT rpc_transport json-rpc && \
    crudini --set /etc/ironic/ironic.conf database connection sqlite:///var/lib/ironic/ironic.db && \
    crudini --set /etc/ironic/ironic.conf dhcp dhcp_provider none && \
    crudini --set /etc/ironic/ironic.conf conductor automated_clean false && \
    crudini --set /etc/ironic/ironic.conf conductor api_url http://172.22.0.1:6385 && \
    crudini --set /etc/ironic/ironic.conf deploy http_url http://172.22.0.1 && \
    crudini --set /etc/ironic/ironic.conf deploy http_root /var/www/html/ && \
    crudini --set /etc/ironic/ironic.conf deploy default_boot_option local && \
    crudini --set /etc/ironic/ironic.conf inspector endpoint_override http://172.22.0.1:5050 && \
    crudini --set /etc/ironic/ironic.conf pxe ipxe_enabled true && \
    crudini --set /etc/ironic/ironic.conf pxe pxe_config_template \$pybasedir/drivers/modules/ipxe_config.template && \
    ironic-dbsync --config-file /etc/ironic/ironic.conf create_schema

COPY ./config /config
COPY ./runironic.sh /bin/runironic
COPY ./runhealthcheck.sh /bin/runhealthcheck

RUN chmod +x /bin/runironic

ENTRYPOINT ["/bin/runironic"]
