#!/usr/bin/bash

. /bin/configure-ironic.sh

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

# Configure HTTP basic auth for json-rpc server
if [ -f "${HTPASSWD_FILE}" ]; then
  set_http_basic_server_auth_strategy json_rpc

  # Access is authenticated, so bind json-rpc server to all IP addresses (not
  # just localhost)
  crudini --del /etc/ironic/ironic.conf json_rpc host_ip
else
  # Access is unauthenticated, so we bind only to localhost - use that as the
  # host name also, so that the client can find the server
  crudini --set /etc/ironic/ironic.conf DEFAULT host localhost
fi

cp -f /tmp/uefi_esp.img /shared/html/uefi_esp.img

# It's possible for the dbsync to fail if mariadb is not up yet, so
# retry until success
until ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade; do
  echo "WARNING: ironic-dbsync failed, retrying"
  sleep 1
done

exec /usr/bin/ironic-conductor ${IRONIC_CONFIG_OPTIONS}
