#!/usr/bin/bash

. /bin/ironic-common.sh

export HTTP_PORT=${HTTP_PORT:-"80"}
DNSMASQ_EXCEPT_INTERFACE=${DNSMASQ_EXCEPT_INTERFACE:-"lo"}

wait_for_interface_or_ip

mkdir -p /shared/tftpboot/EFI/centos
mkdir -p /shared/html/images
mkdir -p /shared/html/pxelinux.cfg

# Copy files to shared mount
cp /tftpboot/undionly.kpxe /tftpboot/ipxe.efi /tftpboot/snponly.efi /shared/tftpboot
cp /tftpboot/BOOTX64.EFI /tftpboot/grubx64.efi /shared/tftpboot
cp /tftpboot/EFI/centos/grub.cfg /shared/tftpboot/EFI/centos/
chmod a+r /shared/tftpboot/BOOTX64.EFI /shared/tftpboot/grubx64.efi /shared/tftpboot/EFI/centos/grub.cfg

# Template and write dnsmasq.conf
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' </etc/dnsmasq.conf.j2 >/etc/dnsmasq.conf

for iface in $( echo "$DNSMASQ_EXCEPT_INTERFACE" | tr ',' ' '); do
    sed -i -e "/^interface=.*/ a\except-interface=${iface}" /etc/dnsmasq.conf
done

exec /usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf
