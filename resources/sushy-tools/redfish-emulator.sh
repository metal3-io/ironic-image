#!/bin/bash

set -eux -o pipefail

CONFIG="${SUSHY_TOOLS_CONFIG:-/root/sushy/conf.py}"
ARGS=()

if [[ -f "${CONFIG}" ]]; then
    ARGS+=("--config" "${CONFIG}")
fi

if [[ ! -f "${CONFIG}" ]] || ! grep -q "^SUSHY_EMULATOR_LISTEN_IP =" -- "${CONFIG}"; then
    # Listen on all interfaces unless explicitly configured otherwise.
    ARGS+=("--interface" "::")
fi

exec /usr/local/bin/sushy-emulator --debug "${ARGS[@]}"
