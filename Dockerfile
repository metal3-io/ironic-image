FROM docker.io/centos:centos7

RUN yum install -y python-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/5609d2e3aee35578e914bcbfac92a46c759c0a31/tripleo_repos/main.py | python - current && \
    yum install -y openstack-ironic-api openstack-ironic-conductor crudini iproute dnsmasq httpd qemu-img-ev iscsi-initiator-utils parted gdisk ipxe-bootimgs psmisc sysvinit-tools mariadb-server python-PyMySQL python2-chardet && \
    yum clean all

RUN mkdir /tftpboot && \
    cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /tftpboot/

RUN cp /etc/ironic/ironic.conf /etc/ironic/ironic.conf_orig && \
    crudini --set /etc/ironic/ironic.conf DEFAULT auth_strategy noauth && \
    crudini --set /etc/ironic/ironic.conf DEFAULT my_ip IRONIC_IP && \
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
    crudini --set /etc/ironic/ironic.conf dhcp dhcp_provider none && \
    crudini --set /etc/ironic/ironic.conf conductor automated_clean false && \
    crudini --set /etc/ironic/ironic.conf conductor api_url http://IRONIC_IP:6385 && \
    crudini --set /etc/ironic/ironic.conf deploy http_url http://IRONIC_IP:HTTP_PORT && \
    crudini --set /etc/ironic/ironic.conf deploy http_root /shared/html/ && \
    crudini --set /etc/ironic/ironic.conf deploy default_boot_option local && \
    crudini --set /etc/ironic/ironic.conf inspector endpoint_override http://IRONIC_IP:5050 && \
    crudini --set /etc/ironic/ironic.conf pxe ipxe_enabled true && \
    crudini --set /etc/ironic/ironic.conf pxe tftp_root /shared/tftpboot && \
    crudini --set /etc/ironic/ironic.conf pxe tftp_master_path /shared/tftpboot && \
    crudini --set /etc/ironic/ironic.conf pxe instance_master_path /shared/html/master_images && \
    crudini --set /etc/ironic/ironic.conf pxe images_path /shared/html/tmp && \
    crudini --set /etc/ironic/ironic.conf pxe pxe_config_template \$pybasedir/drivers/modules/ipxe_config.template

COPY ./runironic.sh /bin/runironic
COPY ./rundnsmasq.sh /bin/rundnsmasq
COPY ./runhttpd.sh /bin/runhttpd
COPY ./runhealthcheck.sh /bin/runhealthcheck

COPY ./dnsmasq.conf /etc/dnsmasq.conf
COPY ./inspector.ipxe /tmp/inspector.ipxe
COPY ./dualboot.ipxe /tmp/dualboot.ipxe

ENTRYPOINT ["/bin/runironic"]
