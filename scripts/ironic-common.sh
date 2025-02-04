#!/usr/bin/bash

set -euxo pipefail

IRONIC_IP="${IRONIC_IP:-}"
PROVISIONING_INTERFACE="${PROVISIONING_INTERFACE:-}"
PROVISIONING_IP="${PROVISIONING_IP:-}"
PROVISIONING_MACS="${PROVISIONING_MACS:-}"
IPXE_CUSTOM_FIRMWARE_DIR="${IPXE_CUSTOM_FIRMWARE_DIR:-/shared/custom_ipxe_firmware}"
CUSTOM_CONFIG_DIR="${CUSTOM_CONFIG_DIR:-/conf}"
CUSTOM_DATA_DIR="${CUSTOM_DATA_DIR:-/data}"
export DNSMASQ_CONF_DIR="${CUSTOM_CONFIG_DIR}/dnsmasq"
export DNSMASQ_DATA_DIR="${CUSTOM_DATA_DIR}/dnsmasq"
export DNSMASQ_TEMP_DIR="${CUSTOM_CONFIG_DIR}/dnsmasq"
export HTTPD_DIR="${CUSTOM_CONFIG_DIR}/httpd"
export HTTPD_CONF_DIR="${HTTPD_DIR}/conf"
export HTTPD_CONF_DIR_D="${HTTPD_DIR}/conf.d"
export IPXE_CONF_DIR="${CUSTOM_CONFIG_DIR}/ipxe"
export IRONIC_CONF_DIR="${CUSTOM_CONFIG_DIR}/ironic"
export IRONIC_DB_DIR="${CUSTOM_DATA_DIR}/db"
export IRONIC_GEN_CERT_DIR="${CUSTOM_DATA_DIR}/auto_gen_certs"
export IRONIC_TMP_DATA_DIR="${CUSTOM_DATA_DIR}/tmp"
export PROBE_CONF_DIR="${CUSTOM_CONFIG_DIR}/probes"

mkdir -p "${IRONIC_CONF_DIR}" "${PROBE_CONF_DIR}" "${HTTPD_CONF_DIR}" \
    "${HTTPD_CONF_DIR_D}" "${DNSMASQ_CONF_DIR}" "${DNSMASQ_TEMP_DIR}" \
    "${IRONIC_DB_DIR}" "${IRONIC_GEN_CERT_DIR}" "${IPXE_CONF_DIR}" \
    "${DNSMASQ_DATA_DIR}" "${IRONIC_TMP_DATA_DIR}"

export HTPASSWD_FILE="${IRONIC_CONF_DIR}/htpasswd"
export LOCAL_DB_URI="sqlite:///${IRONIC_DB_DIR}/ironic.sqlite"

export IRONIC_USE_MARIADB=${IRONIC_USE_MARIADB:-false}

get_provisioning_interface()
{
    if [[ -n "$PROVISIONING_INTERFACE" ]]; then
        # don't override the PROVISIONING_INTERFACE if one is provided
        echo "$PROVISIONING_INTERFACE"
        return
    fi

    local interface="provisioning"

    if [[ -n "${PROVISIONING_IP}" ]]; then
        if ip -br addr show | grep -i " ${PROVISIONING_IP}/" &>/dev/null; then
            interface="$(ip -br addr show | grep -i " ${PROVISIONING_IP}/" | cut -f 1 -d ' ' | cut -f 1 -d '@')"
        fi
    fi

    for mac in ${PROVISIONING_MACS//,/ }; do
        if ip -br link show up | grep -i "$mac" &>/dev/null; then
            interface="$(ip -br link show up | grep -i "$mac" | cut -f 1 -d ' ' | cut -f 1 -d '@')"
            break
        fi
    done

    echo "$interface"
}

PROVISIONING_INTERFACE="$(get_provisioning_interface)"
export PROVISIONING_INTERFACE

export LISTEN_ALL_INTERFACES="${LISTEN_ALL_INTERFACES:-true}"

# Wait for the interface or IP to be up, sets $IRONIC_IP
wait_for_interface_or_ip()
{
    # If $PROVISIONING_IP is specified, then we wait for that to become
    # available on an interface, otherwise we look at $PROVISIONING_INTERFACE
    # for an IP
    if [[ -n "${PROVISIONING_IP}" ]]; then
        # Convert the address using ipcalc which strips out the subnet.
        # For IPv6 addresses, this will give the short-form address
        IRONIC_IP="$(ipcalc "${PROVISIONING_IP}" | grep "^Address:" | awk '{print $2}')"
        export IRONIC_IP
        until grep -F " ${IRONIC_IP}/" <(ip -br addr show); do
            echo "Waiting for ${IRONIC_IP} to be configured on an interface"
            sleep 1
        done
    else
        until [[ -n "$IRONIC_IP" ]]; do
            echo "Waiting for ${PROVISIONING_INTERFACE} interface to be configured"
            IRONIC_IP="$(ip -br add show scope global up dev "${PROVISIONING_INTERFACE}" | awk '{print $3}' | sed -e 's%/.*%%' | head -n 1)"
            export IRONIC_IP
            sleep 1
        done
    fi

    # If the IP contains a colon, then it's an IPv6 address, and the HTTP
    # host needs surrounding with brackets
    if [[ "$IRONIC_IP" =~ .*:.* ]]; then
        export IPV=6
        export IRONIC_URL_HOST="[$IRONIC_IP]"
    else
        export IPV=4
        export IRONIC_URL_HOST="$IRONIC_IP"
    fi
}

render_j2_config()
{
    python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < "$1" > "$2"
}

run_ironic_dbsync()
{
    if [[ "${IRONIC_USE_MARIADB}" == "true" ]]; then
        # It's possible for the dbsync to fail if mariadb is not up yet, so
        # retry until success
        until ironic-dbsync --config-file "${IRONIC_CONF_DIR}/ironic.conf" upgrade; do
            echo "WARNING: ironic-dbsync failed, retrying"
            sleep 1
        done
    else
        # SQLite does not support some statements. Fortunately, we can just
        # create the schema in one go if not already created, instead of going
        # through an upgrade
        cp "/var/lib/ironic/ironic.sqlite" "${IRONIC_DB_DIR}/ironic.sqlite"
        DB_VERSION="$(ironic-dbsync --config-file "${IRONIC_CONF_DIR}/ironic.conf" version)"
        if [[ "${DB_VERSION}" == "None" ]]; then
            ironic-dbsync --config-file "${IRONIC_CONF_DIR}/ironic.conf" create_schema
        fi
    fi
}

# Use the special value "unix" for unix sockets
export IRONIC_PRIVATE_PORT=${IRONIC_PRIVATE_PORT:-unix}

export IRONIC_ACCESS_PORT=${IRONIC_ACCESS_PORT:-6385}
export IRONIC_LISTEN_PORT=${IRONIC_LISTEN_PORT:-$IRONIC_ACCESS_PORT}

export IRONIC_ENABLE_DISCOVERY=${IRONIC_ENABLE_DISCOVERY:-${IRONIC_INSPECTOR_ENABLE_DISCOVERY:-false}}
