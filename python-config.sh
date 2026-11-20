#!/usr/bin/env bash

# Source this file to select the interpreter used by the image.
# PYTHON_VERSION may be supplied as a build override. At runtime, the resolved
# build-time version is persisted under /etc/ironic; otherwise choose the
# supported default for the base image's CentOS major version.
if [[ -z "${PYTHON_VERSION:-}" && -s /etc/ironic/python-version ]]; then
    PYTHON_VERSION="$(</etc/ironic/python-version)"
fi

if [[ -z "${PYTHON_VERSION:-}" ]]; then
    if [[ ! -r /etc/os-release ]]; then
        echo "ERROR: cannot detect the base OS: /etc/os-release is unavailable" >&2
        return 1
    fi

    # shellcheck disable=SC1091
    . /etc/os-release
    case "${VERSION_ID:-}" in
    9|9.*)
        PYTHON_VERSION=3.12
        ;;
    10|10.*)
        PYTHON_VERSION=3.14
        ;;
    *)
        echo "ERROR: unsupported base OS version: ${VERSION_ID:-<unset>}" >&2
        return 1
        ;;
    esac
fi

if [[ ! "${PYTHON_VERSION}" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: invalid PYTHON_VERSION: ${PYTHON_VERSION}" >&2
    return 1
fi

PYTHON_BIN="python${PYTHON_VERSION}"
export PYTHON_VERSION PYTHON_BIN
