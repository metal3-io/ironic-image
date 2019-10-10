#!/usr/bin/bash

. /bin/configure-ironic.sh

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

# Remove log files from last deployment
rm -rf /shared/log/ironic

mkdir -p /shared/log/ironic

/usr/bin/ironic-conductor --log-file /shared/log/ironic/ironic-conductor.log &
/usr/bin/ironic-api --log-file  /shared/log/ironic/ironic-api.log &

/bin/runhealthcheck "ironic" &>/dev/null &

sleep infinity

