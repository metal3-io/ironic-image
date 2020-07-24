#!/usr/bin/bash

. /bin/configure-ironic.sh

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

# If the config file has the json-rpc server bound to a specific address
# (rather than the default ::), use that address as the host name
if bind_addr="$(crudini --get /etc/ironic/ironic.conf json_rpc host_ip 2>/dev/null)"; then
  crudini --set /etc/ironic/ironic.conf DEFAULT host ${bind_addr}
fi

# It's possible for the dbsync to fail if mariadb is not up yet, so
# retry until success
until ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade; do
  echo "WARNING: ironic-dbsync failed, retrying"
  sleep 1
done

exec /usr/bin/ironic-conductor --config-file /etc/ironic/ironic.conf
