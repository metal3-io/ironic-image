#!/usr/bin/bash

. /bin/configure-ironic.sh

exec /usr/bin/ironic-api ${IRONIC_API_CONFIG_OPTIONS}
