#!/usr/bin/bash

. /bin/configure-ironic.sh

crudini --merge /etc/ironic/ironic.conf <<EOF
[json_rpc]
port = 8090
host_ip = 127.0.0.1
EOF

# Remove log files from last deployment
rm -rf /shared/log/ironic
mkdir -p /shared/log/ironic

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

# It's possible for the dbsync to fail if mariadb is not up yet, so
# retry until success
until ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade; do
  echo "WARNING: ironic-dbsync failed, retrying"
  sleep 1
done

# Template and write httpd ironic.conf
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < /etc/httpd-ironic-conductor.conf.j2 > /etc/httpd/conf.d/ironic-conductor.conf
sed -i "/Listen 80/c\#Listen 80" /etc/httpd/conf/httpd.conf


/usr/sbin/httpd

exec /usr/bin/ironic-conductor --config-file /etc/ironic/ironic.conf
