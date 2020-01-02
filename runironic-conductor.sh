#!/usr/bin/bash

. /bin/configure-ironic.sh

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

cp -f /tmp/uefi_esp.img /shared/html/uefi_esp.img

# It's possible for the dbsync to fail if mariadb is not up yet, so
# retry until success
until ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade; do
  echo "WARNING: ironic-dbsync failed, retrying"
  sleep 1
done

exec /usr/bin/ironic-conductor --config-file /etc/ironic/ironic.conf
