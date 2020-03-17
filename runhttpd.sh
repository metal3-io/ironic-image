#!/usr/bin/bash

. /bin/ironic-common.sh

HTTP_PORT=${HTTP_PORT:-"80"}

wait_for_interface_or_ip

mkdir -p /shared/html/redfish
chmod 0777 /shared/html

# Copy files to shared mount
cp /tmp/uefi_esp.img /shared/html/uefi_esp.img

sed -i 's/^Listen .*$/Listen [::]:'"$HTTP_PORT"'/' /etc/httpd/conf/httpd.conf
sed -i -e 's|\(^[[:space:]]*\)\(DocumentRoot\)\(.*\)|\1\2 "/shared/html"|' \
    -e 's|<Directory "/var/www/html">|<Directory "/shared/html">|' \
    -e 's|<Directory "/var/www">|<Directory "/shared">|' /etc/httpd/conf/httpd.conf

# Log to std out/err
sed -i -e 's%^ \+CustomLog.*%    CustomLog /dev/stderr combined%g' /etc/httpd/conf/httpd.conf
sed -i -e 's%^ErrorLog.*%ErrorLog /dev/stderr%g' /etc/httpd/conf/httpd.conf

exec /usr/sbin/httpd -DFOREGROUND
