#!/usr/bin/bash

PROVISIONING_INTERFACE=${PROVISIONING_INTERFACE:-"provisioning"}

HTTP_PORT=${HTTP_PORT:-"80"}
DHCP_RANGE=${DHCP_RANGE:-"172.22.0.10,172.22.0.100"}
DNSMASQ_EXCEPT_INTERFACE=${DNSMASQ_EXCEPT_INTERFACE:-"lo"}

PROVISIONING_IP=$(ip -4 address show dev "$PROVISIONING_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
until [ ! -z "${PROVISIONING_IP}" ]; do
  echo "Waiting for ${PROVISIONING_INTERFACE} interface to be configured"
  sleep 1
  PROVISIONING_IP=$(ip -4 address show dev "$PROVISIONING_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n 1)
done

mkdir -p /shared/tftpboot
mkdir -p /shared/html/images
mkdir -p /shared/html/pxelinux.cfg
mkdir -p /shared/log/dnsmasq

# Copy files to shared mount
cp /usr/share/ipxe/undionly.kpxe /shared/tftpboot
cp /usr/share/ipxe/ipxe-x86_64.efi /shared/tftpboot/ipxe.efi

# Use configured values
sed -i -e s/IRONIC_IP/${PROVISIONING_IP}/g -e s/HTTP_PORT/${HTTP_PORT}/g \
       -e s/DHCP_RANGE/${DHCP_RANGE}/g -e s/PROVISIONING_INTERFACE/${PROVISIONING_INTERFACE}/g \
       /etc/dnsmasq.conf
for iface in $( echo "$DNSMASQ_EXCEPT_INTERFACE" | tr ',' ' '); do
    sed -i -e "/^interface=.*/ a\except-interface=${iface}" /etc/dnsmasq.conf
done

# Allow access to dhcp and tftp server for pxeboot
for port in 67 69 ; do
    if ! iptables -C INPUT -i "$PROVISIONING_INTERFACE" -p udp --dport "$port" -j ACCEPT 2>/dev/null ; then
        iptables -I INPUT -i "$PROVISIONING_INTERFACE" -p udp --dport "$port" -j ACCEPT
    fi
done

/usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf 2>&1 | tee /shared/log/dnsmasq/dnsmasq.log &
/bin/runhealthcheck "dnsmasq" &>/dev/null &
sleep infinity

