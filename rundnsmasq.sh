#!/usr/bin/bash

IP=${IP:-"172.22.0.1"}
HTTP_PORT=${HTTP_PORT:-"80"}
DHCP_RANGE=${DHCP_RANGE:-"172.22.0.10,172.22.0.100"}
INTERFACE=${INTERFACE:-"provisioning"}
EXCEPT_INTERFACE=${EXCEPT_INTERFACE:-"lo"}
DNSERVERS=${DNSERVERS:-}
DOMAIN=${DOMAIN:-}

mkdir -p /shared/tftpboot
mkdir -p /shared/log/dnsmasq

# Copy files to shared mount
cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /shared/tftpboot

# Use configured values
sed -i -e s/IRONIC_IP/$IP/g -e s/HTTP_PORT/$HTTP_PORT/g \
       -e s/DHCP_RANGE/$DHCP_RANGE/g -e s/INTERFACE/$INTERFACE/g /etc/dnsmasq.conf
for iface in $( echo $EXCEPT_INTERFACE | tr ',' ' '); do
    sed -i -e "/^interface=.*/ a\except-interface=$iface" /etc/dnsmasq.conf
done

# Offer dns server and domain, if present
if [ ! -z "$DNSSERVERS" ] && [ ! -z "$DOMAIN" ]  ; then
    sed -i "s/dhcp-option=6/#dhcp-option=6/" /etc/dnsmasq.conf
    echo dhcp-option=option:domain-name,$DOMAIN >> /etc/dnsmasq.conf
    for DNSSERVER in $(echo $DNSSERVERS | sed 's/,/ /') ; do 
      echo dhcp-option=option:dns-server,$DNSSERVER >> /etc/dnsmasq.conf
    done
fi

# Allow access to dhcp and tftp server for pxeboot
for port in 67 69 ; do
    if ! iptables -C INPUT -i $INTERFACE -p udp --dport $port -j ACCEPT 2>/dev/null ; then
        iptables -I INPUT -i $INTERFACE -p udp --dport $port -j ACCEPT
    fi
done

/usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf 2>&1 | tee /shared/log/dnsmasq/dnsmasq.log &
/bin/runhealthcheck "dnsmasq" &>/dev/null &
sleep infinity

