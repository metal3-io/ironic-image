#!/usr/bin/bash

. /bin/ironic-common.sh

export HTTP_PORT=${HTTP_PORT:-"80"}
export DNSMASQ_EXCEPT_INTERFACE=${DNSMASQ_EXCEPT_INTERFACE:-"lo"}

wait_for_interface_or_ip

mkdir -p /shared/tftpboot
mkdir -p /shared/html/images
mkdir -p /shared/html/pxelinux.cfg
mkdir -p /shared/log/dnsmasq

# Copy files to shared mount
# TODO(stbenjam): Add snponly.efi to this list when it's available from EL8 packages.
cp /usr/share/ipxe/undionly.kpxe /shared/tftpboot
if [ -f "/usr/share/ipxe/ipxe.efi" ]; then
    cp /usr/share/ipxe/ipxe.efi /shared/tftpboot/ipxe.efi
elif [ -f "/usr/share/ipxe/ipxe-x86_64.efi" ]; then
    cp  /usr/share/ipxe/ipxe-x86_64.efi /shared/tftpboot/ipxe.efi
else
    echo "Fatal Error - Failed to find ipxe binary"
    exit 1
fi

# Template and write dnsmasq.conf
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' </etc/dnsmasq.conf.j2 >/etc/dnsmasq.conf

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
