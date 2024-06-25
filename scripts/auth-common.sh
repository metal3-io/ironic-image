#!/usr/bin/bash

set -euxo pipefail

export IRONIC_REVERSE_PROXY_SETUP=${IRONIC_REVERSE_PROXY_SETUP:-false}

# Backward compatibility
if [[ "${IRONIC_DEPLOYMENT:-}" == "Conductor" ]]; then
    export IRONIC_EXPOSE_JSON_RPC=true
else
    export IRONIC_EXPOSE_JSON_RPC="${IRONIC_EXPOSE_JSON_RPC:-false}"
fi

IRONIC_HTPASSWD_FILE=/etc/ironic/htpasswd
if [[ -f "/auth/ironic/htpasswd" ]]; then
    IRONIC_HTPASSWD=$(</auth/ironic/htpasswd)
fi
if [[ -f "/auth/ironic-rpc/htpasswd" ]]; then
    IRONIC_RPC_HTPASSWD=$(</auth/ironic-rpc/htpasswd)
fi
export IRONIC_HTPASSWD=${IRONIC_HTPASSWD:-${HTTP_BASIC_HTPASSWD:-}}
export IRONIC_RPC_HTPASSWD=${IRONIC_RPC_HTPASSWD:-${IRONIC_HTPASSWD}}

IRONIC_CONFIG=/etc/ironic/ironic.conf


configure_json_rpc_auth()
{
    if [[ "${IRONIC_EXPOSE_JSON_RPC}" == "true" ]]; then
        local auth_config_file="/auth/ironic-rpc/auth-config"
        local username_file="/auth/ironic-rpc/username"
        local password_file="/auth/ironic-rpc/password"
        if [[ -f "${username_file}" ]] && [[ -f "${password_file}" ]]; then
            crudini --set "${IRONIC_CONFIG}" json_rpc username "$(<${username_file})"
            set +x
            crudini --set "${IRONIC_CONFIG}" json_rpc password "$(<${password_file})"
            set -x
        elif [[ -f "${auth_config_file}" ]]; then
            echo "WARNING: using auth-config is deprecated, mount a secret directly"
            # Merge configurations in the "auth" directory into the default ironic configuration file
            crudini --merge "${IRONIC_CONFIG}" < "${auth_config_file}"
        else
            echo "FATAL: no client-side credentials provided for JSON RPC"
            exit 1
        fi

        if [[ -z "${IRONIC_RPC_HTPASSWD}" ]]; then
            if [[ -f "${username_file}" ]] && [[ -f "${password_file}" ]]; then
                htpasswd -c -i -B "${IRONIC_HTPASSWD_FILE}-rpc" "$(<${username_file})" <"${password_file}"
            else
                echo "FATAL: enabling JSON RPC requires authentication"
                exit 1
            fi
        else
            printf "%s\n" "${IRONIC_RPC_HTPASSWD}" > "${IRONIC_HTPASSWD_FILE}-rpc"
        fi
    fi
}

configure_ironic_auth()
{
    # Configure HTTP basic auth for API server
    if [[ -n "${IRONIC_HTPASSWD}" ]]; then
        printf "%s\n" "${IRONIC_HTPASSWD}" > "${IRONIC_HTPASSWD_FILE}"
        if [[ "${IRONIC_REVERSE_PROXY_SETUP}" == "false" ]]; then
            crudini --set "${IRONIC_CONFIG}" DEFAULT auth_strategy http_basic
            crudini --set "${IRONIC_CONFIG}" DEFAULT http_basic_auth_user_file "${IRONIC_HTPASSWD_FILE}"
        fi
    fi
}

write_htpasswd_files()
{
    if [[ -n "${IRONIC_HTPASSWD:-}" ]]; then
        printf "%s\n" "${IRONIC_HTPASSWD}" > "${IRONIC_HTPASSWD_FILE}"
    fi
}
