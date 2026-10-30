#!/usr/bin/bash

set -euxo pipefail

# shellcheck disable=SC1091
. /bin/configure-ironic.sh

# Ramdisk logs
mkdir -p /shared/log/ironic/deploy

# The original ironic.conf is empty, and can be found in ironic.conf.orig
render_j2_config "/etc/ironic/ironic.conf.j2" \
    "${IRONIC_CONF_DIR}/ironic.conf"

if [[ "${IRONIC_EXPOSE_JSON_RPC}" == "true" ]]; then
    configure_json_rpc_auth
fi

if [[ "${IRONIC_NETWORKING_ENABLED}" == "true" ]]; then
    configure_json_rpc_auth "ironic_networking_json_rpc"
fi

if [[ "${IRONIC_INJECT_IPA}" == "true" ]]; then
    generate_cacert_bundle_initrd /shared/html/ipa-cacert-bundle
fi

configure_ironic_auth

TMP_DIR="$(mktemp -d)"
IRONIC_ENV_FILE="${TMP_DIR}/ironic.env"
cat <<EOF > "${IRONIC_ENV_FILE}"
IRONIC_USE_MARIADB=${IRONIC_USE_MARIADB}
IRONIC_DBSYNC_TIMEOUT=${IRONIC_DBSYNC_TIMEOUT}
IRONIC_DBSYNC_INTERVAL=${IRONIC_DBSYNC_INTERVAL}
IRONIC_DB_DIR=${IRONIC_DB_DIR}
IRONIC_CONF_DIR=${IRONIC_CONF_DIR}
BMC_CACERTS_PATH=${BMC_CACERTS_PATH}
WEBSERVER_CACERT_FILE=${WEBSERVER_CACERT_FILE:-}
RESTART_ON_CERT_UPDATE=${RESTART_CONTAINER_CERTIFICATE_UPDATED}
NO_PROXY=${NO_PROXY}
EOF

copy_atomic "${IRONIC_ENV_FILE}" "/conf/ironic/ironic.env"
rm -rf "${TMP_DIR}"
