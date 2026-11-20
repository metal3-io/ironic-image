#!/usr/bin/env bash

# Source this file to select the interpreter used by the image.
# PYTHON_VERSION may be supplied as a build override. At runtime, the resolved
# build-time version is persisted under /etc/ironic; otherwise choose the
# supported default for the base image's major version.
if [[ ! -r /etc/os-release ]]; then
    echo "ERROR: cannot detect the base OS: /etc/os-release is unavailable" >&2
    return 1
fi

# shellcheck disable=SC1091
. /etc/os-release
if [[ "${ID:-}" != "centos" ]]; then
    echo "WARNING: base OS distribution '${ID:-<unset>}' is not CentOS; this is an unsupported upstream distro, so Python selection is best-effort. Set PYTHON_VERSION explicitly if needed." >&2
fi

if [[ -z "${PYTHON_VERSION:-}" ]]; then
    if [[ -s /etc/ironic/python-version ]]; then
        PYTHON_VERSION="$(</etc/ironic/python-version)"
    else
        case "${VERSION_ID:-}" in
        9|9.*)
            PYTHON_VERSION=3.12
            ;;
        10|10.*)
            PYTHON_VERSION=3.14
            ;;
        *)
            echo "ERROR: cannot derive the default Python version from base OS VERSION_ID '${VERSION_ID:-<unset>}'; set PYTHON_VERSION explicitly" >&2
            return 1
            ;;
        esac
    fi
fi

if [[ ! "${PYTHON_VERSION}" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: invalid PYTHON_VERSION: ${PYTHON_VERSION}" >&2
    return 1
fi

export PYTHON_VERSION
