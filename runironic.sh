#!/usr/bin/bash

IP=${IP:-"172.22.0.1"}
HTTP_PORT=${HTTP_PORT:-"80"}
INTERFACE=${INTERFACE:-"provisioning"}

sed -i -e s/IRONIC_IP/$IP/g -e s/HTTP_PORT/$HTTP_PORT/g /etc/ironic/ironic.conf 

# Allow access to Ironic
if ! iptables -C INPUT -i $INTERFACE -p tcp -m tcp --dport 5050 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i $INTERFACE -p tcp -m tcp --dport 5050 -j ACCEPT
fi

/usr/bin/python2 /usr/bin/ironic-conductor > /var/log/ironic-conductor.out 2>&1 &

/usr/bin/python2 /usr/bin/ironic-api > /var/log/ironic-api.out 2>&1 &
/bin/runhealthcheck "ironic" &>/dev/null &
sleep infinity

