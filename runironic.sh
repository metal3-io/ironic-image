#!/usr/bin/bash

. /bin/configure-ironic.sh

# Allow access to Ironic
if ! iptables -C INPUT -i "$PROVISIONING_INTERFACE" -p tcp -m tcp --dport 6385 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i "$PROVISIONING_INTERFACE" -p tcp -m tcp --dport 6385 -j ACCEPT
fi

# Allow access to mDNS
if ! iptables -C INPUT -i $PROVISIONING_INTERFACE -p udp --dport 5353 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i $PROVISIONING_INTERFACE -p udp --dport 5353 -j ACCEPT
fi
if ! iptables -C OUTPUT -p udp --dport 5353 -j ACCEPT > /dev/null 2>&1; then
    iptables -I OUTPUT -p udp --dport 5353 -j ACCEPT
fi

ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade

# Remove log files from last deployment
rm -rf /shared/log/ironic

mkdir -p /shared/log/ironic

/usr/bin/ironic-conductor --log-file /shared/log/ironic/ironic-conductor.log &
/usr/bin/ironic-api --log-file  /shared/log/ironic/ironic-api.log &

/bin/runhealthcheck "ironic" &>/dev/null &

sleep infinity

