#!/usr/bin/bash

. /bin/ironic-common.sh

export HTTP_PORT=${HTTP_PORT:-"80"}

wait_for_interface_or_ip

mkdir -p /shared/tftpboot
mkdir -p /shared/html/images
mkdir -p /shared/html/pxelinux.cfg

# Copy files to shared mount
cp /tftpboot/undionly.kpxe /tftpboot/ipxe.efi /tftpboot/snponly.efi /shared/tftpboot

# Template and write dnsmasq.conf
jinjarender </etc/dnsmasq.conf.j2 >/etc/dnsmasq.conf

exec /usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf
