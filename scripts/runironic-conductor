#!/usr/bin/bash

export IRONIC_DEPLOYMENT="Conductor"

. /bin/configure-ironic.sh

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

run_ironic_dbsync

if [[ "$IRONIC_TLS_SETUP" == "true"  && "${RESTART_CONTAINER_CERTIFICATE_UPDATED}" == "true" ]]; then
    inotifywait -m -e delete_self "${IRONIC_CERT_FILE}" | while read file event; do
     kill $(pgrep ironic)
    done &
fi

exec /usr/bin/ironic-conductor
