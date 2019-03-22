#!/usr/bin/bash

cp /shared/dnsmasq.conf /etc/dnsmasq.conf
cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /shared/tftpboot

/usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf &
/bin/runhealthcheck "dnsmasq" &>/dev/null &
sleep infinity

