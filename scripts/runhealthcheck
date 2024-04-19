#!/bin/bash
set -ex

IRONIC_INSPECTOR_CACERT_FILE=/certs/ca/ironic-inspector/tls.crt
IRONIC_INSPECTOR_CERT_FILE=/certs/ironic-inspector/tls.crt

. /bin/ironic-common.sh
get_ironic_ip
#If the IP is not set, we are not running yet
[ -z $IRONIC_IP ] && exit 1

if [ ! -f "$IRONIC_INSPECTOR_CERT_FILE" ] && [ ! -f "$IRONIC_INSPECTOR_CACERT_FILE" ]; then
    curl -s http://${IRONIC_URL_HOST}:5050
else
    CACERT_FILE="${IRONIC_INSPECTOR_CACERT_FILE}"
    if [ ! -f "${IRONIC_INSPECTOR_CACERT_FILE}" ]; then
        CACERT_FILE="${IRONIC_INSPECTOR_CERT_FILE}"
    fi
    curl --cacert "$CACERT_FILE" -s "https://${IRONIC_URL_HOST}:5050"
fi
