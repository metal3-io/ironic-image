#!/usr/bin/bash

export IRONIC_DEPLOYMENT="API"

. /bin/configure-ironic.sh

exec /usr/bin/ironic-api --config-file /usr/share/ironic/ironic-dist.conf ${IRONIC_CONFIG_OPTIONS}
