#!/usr/bin/bash

. /bin/configure-ironic.sh

# Allow access to Ironic
if ! iptables -C INPUT -i "$PROVISIONING_INTERFACE" -p tcp -m tcp --dport 6385 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i "$PROVISIONING_INTERFACE" -p tcp -m tcp --dport 6385 -j ACCEPT
fi

exec /usr/bin/ironic-api --config-file /etc/ironic/ironic.conf \
    --log-file /shared/log/ironic/ironic-api.log
