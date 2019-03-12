#!/usr/bin/bash

set -x

# Optionally configure ironic if the environment variable is set.
if [ ! -e "$CONFIGURE_IRONIC" ] ; then
    /config/configure_ironic.sh
fi

/usr/bin/python2 /usr/bin/ironic-conductor > /var/log/ironic-conductor.out 2>&1 &
/usr/bin/python2 /usr/bin/ironic-api > /var/log/ironic-api.out 2>&1 &
/usr/sbin/httpd > /var/log/httpd.out 2>&1 &
/usr/sbin/dnsmasq -d -q -C /etc/dnsmasq.conf > /var/log/dnsmasq.out 2>&1 &
/bin/runhealthcheck &
sleep infinity
