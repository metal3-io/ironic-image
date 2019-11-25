#!/usr/bin/bash

. /bin/ironic-common.sh

HTTP_PORT=${HTTP_PORT:-"80"}
DHCP_RANGE=${DHCP_RANGE:-"172.22.0.10,172.22.0.100"}
DNSMASQ_EXCEPT_INTERFACE=${DNSMASQ_EXCEPT_INTERFACE:-"lo"}

wait_for_interface_or_ip

mkdir -p /shared/tftpboot
mkdir -p /shared/html/images
mkdir -p /shared/html/pxelinux.cfg
mkdir -p /shared/log/dnsmasq

# Copy files to shared mount
cp /tftpboot/undionly.kpxe /tftpboot/ipxe.efi /tftpboot/snponly.efi /shared/tftpboot

# Copy IPv4 or IPv6 config
cp /etc/dnsmasq.conf.ipv$IPV /etc/dnsmasq.conf

# Use configured values
sed -i -e s/IRONIC_URL_HOST/${IRONIC_URL_HOST}/g -e s/HTTP_PORT/${HTTP_PORT}/g \
       -e s/DHCP_RANGE/${DHCP_RANGE}/g -e s/PROVISIONING_INTERFACE/${PROVISIONING_INTERFACE}/g \
       /etc/dnsmasq.conf
for iface in $( echo "$DNSMASQ_EXCEPT_INTERFACE" | tr ',' ' '); do
    sed -i -e "/^interface=.*/ a\except-interface=${iface}" /etc/dnsmasq.conf
done

/usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf 2>&1 | tee /shared/log/dnsmasq/dnsmasq.log &
/bin/runhealthcheck "dnsmasq" &>/dev/null &
sleep infinity
