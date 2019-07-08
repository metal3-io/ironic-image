#!/usr/bin/bash

. /bin/configure-ironic.sh

# Allow access to mDNS
if ! iptables -C INPUT -i $PROVISIONING_INTERFACE -p udp --dport 5353 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i $PROVISIONING_INTERFACE -p udp --dport 5353 -j ACCEPT
fi
if ! iptables -C OUTPUT -p udp --dport 5353 -j ACCEPT > /dev/null 2>&1; then
    iptables -I OUTPUT -p udp --dport 5353 -j ACCEPT
fi

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

exec /usr/bin/ironic-conductor --config-file /etc/ironic/ironic.conf \
    --log-file /shared/log/ironic/ironic-conductor.log
