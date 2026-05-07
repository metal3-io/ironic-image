#!/usr/bin/env bash

# This file contains image building code shared between BMO and IrSO tests.
# It's designed to be sourced, not executed directly.

build_ironic_image() {
    declare -a build_args
    declare -a to_delete

    echo "Building ironic image: ${IRONIC_CUSTOM_IMAGE}"

    if [[ -n "${IRONIC_SOURCE:-}" ]]; then
        if [[ -d "${IRONIC_SOURCE}" ]]; then
            cp -ra "${IRONIC_SOURCE}" sources/ironic
            rm -rf sources/ironic/.tox
            to_delete+=(sources/ironic)
        fi
        build_args+=(--build-arg IRONIC_SOURCE=ironic)
    fi
    if [[ -n "${SUSHY_SOURCE:-}" ]]; then
        if [[ -d "${SUSHY_SOURCE}" ]]; then
            cp -ra "${SUSHY_SOURCE}" sources/sushy
            rm -rf sources/sushy/.tox
            to_delete+=(sources/sushy)
        fi
        build_args+=(--build-arg SUSHY_SOURCE=sushy)
    fi
    if [[ -n "${NGS_SOURCE:-}" ]]; then
        if [[ -d "${NGS_SOURCE}" ]]; then
            cp -ra "${NGS_SOURCE}" sources/networking-generic-switch
            rm -rf sources/networking-generic-switch/.tox
            to_delete+=(sources/networking-generic-switch)
        fi
        build_args+=(--build-arg NGS_SOURCE=networking-generic-switch)
    fi

    "${CONTAINER_RUNTIME}" build -t "${IRONIC_CUSTOM_IMAGE}" "${build_args[@]}" .
    if [[ -n "${to_delete[*]}" ]]; then
        rm -rf "${to_delete[@]}"
    fi
}
