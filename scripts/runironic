#!/usr/bin/bash

# These settings must go before configure-ironic since it has different
# defaults.
export IRONIC_USE_MARIADB=${IRONIC_USE_MARIADB:-false}
export IRONIC_EXPOSE_JSON_RPC=${IRONIC_EXPOSE_JSON_RPC:-false}

. /bin/configure-ironic.sh

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

run_ironic_dbsync

if [[ "$IRONIC_TLS_SETUP" == "true"  && "${RESTART_CONTAINER_CERTIFICATE_UPDATED}" == "true" ]]; then
    inotifywait -m -e delete_self "${IRONIC_CERT_FILE}" | while read file event; do
     kill $(pgrep ironic)
    done &
fi

exec /usr/bin/ironic
