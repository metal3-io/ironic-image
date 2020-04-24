#!/usr/bin/bash

. /bin/ironic-common.sh

HTTP_PORT=${HTTP_PORT:-"80"}

# SSH key to use for debugging the ramdisk (public key contents)
IRONIC_RAMDISK_SSH_KEY=${IRONIC_RAMDISK_SSH_KEY:-}

if [ -n "$IRONIC_RAMDISK_SSH_KEY" ]; then
    # SELinux prevents root login via SSH in some cases
    KERNEL_PARAMS="sshkey=\"$IRONIC_RAMDISK_SSH_KEY\" selinux=0"
fi

wait_for_interface_or_ip

mkdir -p /shared/html
chmod 0777 /shared/html

# Copy files to shared mount
cp /tmp/inspector.ipxe /shared/html/inspector.ipxe
cp /tmp/dualboot.ipxe /shared/html/dualboot.ipxe
cp /tmp/uefi_esp.img /shared/html/uefi_esp.img

# Use configured values
sed -i -e s/IRONIC_IP/${IRONIC_URL_HOST}/g \
    -e s/HTTP_PORT/${HTTP_PORT}/g \
    -e "s/KERNEL_PARAMS/${KERNEL_PARAMS:-}/g" \
    /shared/html/inspector.ipxe

sed -i 's/^Listen .*$/Listen [::]:'"$HTTP_PORT"'/' /etc/httpd/conf/httpd.conf
sed -i -e 's|\(^[[:space:]]*\)\(DocumentRoot\)\(.*\)|\1\2 "/shared/html"|' \
    -e 's|<Directory "/var/www/html">|<Directory "/shared/html">|' \
    -e 's|<Directory "/var/www">|<Directory "/shared">|' /etc/httpd/conf/httpd.conf

# Log to std out/err
sed -i -e 's%^ \+CustomLog.*%    CustomLog /dev/stderr combined%g' /etc/httpd/conf/httpd.conf
sed -i -e 's%^ErrorLog.*%ErrorLog /dev/stderr%g' /etc/httpd/conf/httpd.conf

exec /usr/sbin/httpd -DFOREGROUND
