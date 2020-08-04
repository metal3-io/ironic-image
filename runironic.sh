#!/usr/bin/bash

. /bin/configure-ironic.sh

crudini --set /etc/ironic/ironic.conf DEFAULT host localhost

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

# Remove log files from last deployment
rm -rf /shared/log/ironic

mkdir -p /shared/log/ironic

/usr/bin/ironic-conductor ${IRONIC_CONFIG_OPTIONS} &
/usr/bin/ironic-api --config-file /usr/share/ironic/ironic-dist.conf ${IRONIC_CONFIG_OPTIONS} &

sleep infinity

