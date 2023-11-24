#!/bin/bash

set -eux -o pipefail

CONFIG="${SUSHY_TOOLS_CONFIG:-/root/sushy/conf.py}"
ARGS=

if [[ -f "${CONFIG}" ]]; then
    ARGS="${ARGS} --config ${CONFIG}"
fi

if [[ ! -f "${CONFIG}" ]] || ! grep -q "^SUSHY_EMULATOR_LISTEN_IP =" "${CONFIG}"; then
    # Listen on all interfaces unless explicitly configured otherwise.
    ARGS="${ARGS} --interface ::"
fi

# shellcheck disable=SC2086
exec /usr/local/bin/sushy-emulator --debug $ARGS
