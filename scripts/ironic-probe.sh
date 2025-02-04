#!/bin/bash

set -eu -o pipefail

# shellcheck disable=SC1091
. /bin/ironic-common.sh
# shellcheck disable=SC1091
. /bin/auth-common.sh

PROBE_CURL_ARGS=
if [[ "${IRONIC_REVERSE_PROXY_SETUP}" == "true" ]]; then
    if [[ "${IRONIC_PRIVATE_PORT}" == "unix" ]]; then
        PROBE_URL="http://127.0.0.1:6385"
        PROBE_CURL_ARGS="--unix-socket /shared/ironic.sock"
    else
        PROBE_URL="http://127.0.0.1:${IRONIC_PRIVATE_PORT}"
    fi
else
        PROBE_URL="${IRONIC_BASE_URL}"
fi

# shellcheck disable=SC2086
curl -sSf ${PROBE_CURL_ARGS} "${PROBE_URL}"
