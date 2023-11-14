#!/usr/bin/bash

set -euxo pipefail

export IRONIC_HTPASSWD=${IRONIC_HTPASSWD:-${HTTP_BASIC_HTPASSWD:-}}
export INSPECTOR_HTPASSWD=${INSPECTOR_HTPASSWD:-${HTTP_BASIC_HTPASSWD:-}}
export IRONIC_DEPLOYMENT="${IRONIC_DEPLOYMENT:-}"
export IRONIC_REVERSE_PROXY_SETUP=${IRONIC_REVERSE_PROXY_SETUP:-false}
export INSPECTOR_REVERSE_PROXY_SETUP=${INSPECTOR_REVERSE_PROXY_SETUP:-false}

IRONIC_HTPASSWD_FILE=/etc/ironic/htpasswd
INSPECTOR_HTPASSWD_FILE=/etc/ironic-inspector/htpasswd

configure_client_basic_auth()
{
    local auth_config_file="/auth/$1/auth-config"
    local dest="${2:-/etc/ironic/ironic.conf}"
    if [[ -f "${auth_config_file}" ]]; then
        # Merge configurations in the "auth" directory into the default ironic configuration file because there is no way to choose the configuration file
        # when running the api as a WSGI app.
        crudini --merge "${dest}" < "${auth_config_file}"
    fi
}

configure_json_rpc_auth()
{
    export JSON_RPC_AUTH_STRATEGY="noauth"
    if [[ -n "${IRONIC_HTPASSWD}" ]]; then
        if [[ "${IRONIC_DEPLOYMENT}" == "Conductor" ]]; then
            export JSON_RPC_AUTH_STRATEGY="http_basic"
            printf "%s\n" "${IRONIC_HTPASSWD}" > "${IRONIC_HTPASSWD_FILE}-rpc"
        else
            printf "%s\n" "${IRONIC_HTPASSWD}" > "${IRONIC_HTPASSWD_FILE}"
        fi
    fi
}

configure_ironic_auth()
{
    local config=/etc/ironic/ironic.conf
    # Configure HTTP basic auth for API server
    if [[ -n "${IRONIC_HTPASSWD}" ]]; then
        printf "%s\n" "${IRONIC_HTPASSWD}" > "${IRONIC_HTPASSWD_FILE}"
        if [[ "${IRONIC_REVERSE_PROXY_SETUP}" == "false" ]]; then
            crudini --set "${config}" DEFAULT auth_strategy http_basic
            crudini --set "${config}" DEFAULT http_basic_auth_user_file "${IRONIC_HTPASSWD_FILE}"
        fi
    fi
}

configure_inspector_auth()
{
    local config=/etc/ironic-inspector/ironic-inspector.conf
    if [[ -n "${INSPECTOR_HTPASSWD}" ]]; then
        printf "%s\n" "${INSPECTOR_HTPASSWD}" > "${INSPECTOR_HTPASSWD_FILE}"
        if [[ "${INSPECTOR_REVERSE_PROXY_SETUP}" == "false" ]]; then
            crudini --set "${config}" DEFAULT auth_strategy http_basic
            crudini --set "${config}" DEFAULT http_basic_auth_user_file "${INSPECTOR_HTPASSWD_FILE}"
        fi
    fi
}

write_htpasswd_files()
{
    if [[ -n "${IRONIC_HTPASSWD:-}" ]]; then
        printf "%s\n" "${IRONIC_HTPASSWD}" > "${IRONIC_HTPASSWD_FILE}"
    fi
    if [[ -n "${INSPECTOR_HTPASSWD:-}" ]]; then
        printf "%s\n" "${INSPECTOR_HTPASSWD}" > "${INSPECTOR_HTPASSWD_FILE}"
    fi
}
