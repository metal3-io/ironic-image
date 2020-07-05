#!/usr/bin/bash

. /bin/ironic-common.sh

HTTP_PORT=${HTTP_PORT:-"80"}

wait_for_interface_or_ip

mkdir -p /shared/html
chmod 0777 /shared/html

# Copy files to shared mount
cp /tmp/inspector.ipxe /shared/html/inspector.ipxe
cp /tmp/dualboot.ipxe /shared/html/dualboot.ipxe
cp /tmp/uefi_esp.img /shared/html/uefi_esp.img

# Use configured values
sed -i -e s/IRONIC_IP/${IRONIC_URL_HOST}/g -e s/HTTP_PORT/${HTTP_PORT}/g /shared/html/inspector.ipxe

jinjarender </etc/httpd/conf.d/ironic-image.conf.j2 >/etc/httpd/conf.d/ironic-image.conf

exec /usr/sbin/httpd -DFOREGROUND
