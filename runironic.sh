#!/usr/bin/bash

. /bin/configure-ironic.sh

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

# Remove log files from last deployment
rm -rf /shared/log/ironic

mkdir -p /shared/log/ironic

/usr/bin/ironic-conductor &
/usr/bin/ironic-api &

/bin/runhealthcheck "ironic" &>/dev/null &

sleep infinity

