#!/usr/bin/bash

export IRONIC_DEPLOYMENT="Combined"

. /bin/configure-ironic.sh

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

# Remove log files from last deployment
rm -rf /shared/log/ironic

mkdir -p /shared/log/ironic

/usr/bin/ironic-conductor ${IRONIC_CONFIG_OPTIONS} &
/usr/bin/ironic-api --config-file /usr/share/ironic/ironic-dist.conf ${IRONIC_CONFIG_OPTIONS} &

wait -n
