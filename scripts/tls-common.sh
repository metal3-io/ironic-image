#!/bin/bash

export IRONIC_INSECURE=${IRONIC_INSECURE:-false}
export IRONIC_SSL_PROTOCOL=${IRONIC_SSL_PROTOCOL:-"-ALL +TLSv1.2 +TLSv1.3"}
export IPXE_SSL_PROTOCOL=${IPXE_SSL_PROTOCOL:-"-ALL +TLSv1.2 +TLSv1.3"}
export IRONIC_VMEDIA_SSL_PROTOCOL=${IRONIC_VMEDIA_SSL_PROTOCOL:-"ALL"}

export DEFAULT_CACERT_BUNDLE=${DEFAULT_CACERT_BUNDLE:-"/etc/ssl/cert.pem"}

# Node image storage is using the same cert and port as the API
export IRONIC_CERT_FILE=/certs/ironic/tls.crt
export IRONIC_KEY_FILE=/certs/ironic/tls.key

export IRONIC_VMEDIA_CERT_FILE=/certs/vmedia/tls.crt
export IRONIC_VMEDIA_KEY_FILE=/certs/vmedia/tls.key

export IPXE_CERT_FILE=/certs/ipxe/tls.crt
export IPXE_KEY_FILE=/certs/ipxe/tls.key

export RESTART_CONTAINER_CERTIFICATE_UPDATED=${RESTART_CONTAINER_CERTIFICATE_UPDATED:-"false"}

# By default every cert has to be signed with Ironic's
# CA otherwise node image and IPA verification would fail
export MARIADB_CACERT_FILE=/certs/ca/mariadb/tls.crt
export BMC_CACERTS_PATH=/certs/ca/bmc
export BMC_CACERT_FILE=/conf/bmc-tls.pem
export IRONIC_CACERT_FILE=${IRONIC_CACERT_FILE:-"/certs/ca/ironic/tls.crt"}
export IPA_CACERT_FILE=/conf/ipa-tls.pem

export IPXE_TLS_PORT="${IPXE_TLS_PORT:-8084}"

if [[ -f "$IRONIC_CERT_FILE" ]] && [[ ! -f "$IRONIC_KEY_FILE" ]]; then
    echo "Missing TLS Certificate key file $IRONIC_KEY_FILE"
    exit 1
fi
if [[ ! -f "$IRONIC_CERT_FILE" ]] && [[ -f "$IRONIC_KEY_FILE" ]]; then
    echo "Missing TLS Certificate file $IRONIC_CERT_FILE"
    exit 1
fi

if [[ -f "$IRONIC_VMEDIA_CERT_FILE" ]] && [[ ! -f "$IRONIC_VMEDIA_KEY_FILE" ]]; then
    echo "Missing TLS Certificate key file $IRONIC_VMEDIA_KEY_FILE"
    exit 1
fi
if [[ ! -f "$IRONIC_VMEDIA_CERT_FILE" ]] && [[ -f "$IRONIC_VMEDIA_KEY_FILE" ]]; then
    echo "Missing TLS Certificate file $IRONIC_VMEDIA_CERT_FILE"
    exit 1
fi

if [[ -f "$IPXE_CERT_FILE" ]] && [[ ! -f "$IPXE_KEY_FILE" ]]; then
    echo "Missing TLS Certificate key file $IPXE_KEY_FILE"
    exit 1
fi
if [[ ! -f "$IPXE_CERT_FILE" ]] && [[ -f "$IPXE_KEY_FILE" ]]; then
    echo "Missing TLS Certificate file $IPXE_CERT_FILE"
    exit 1
fi

copy_atomic()
{
    local src="$1"
    local dest="$2"
    local tmpdest

    tmpdest=$(mktemp "$dest.XXX")
    cp "$src" "$tmpdest"
    # Hard linking is atomic, but only works on the same volume
    ln -f "$tmpdest" "$dest"
    rm -f "$tmpdest"
}

if [[ -f "$IRONIC_CERT_FILE" ]] || [[ -f "$IRONIC_CACERT_FILE" ]]; then
    export IRONIC_TLS_SETUP="true"
    export IRONIC_SCHEME="https"
    if [[ ! -f "$IRONIC_CACERT_FILE" ]]; then
        # For missing cacert file, change the var to writable path
        export IRONIC_CACERT_FILE=/conf/certs/ca/ironic/tls.crt
        mkdir -p "$(dirname "${IRONIC_CACERT_FILE}")"
        copy_atomic "$IRONIC_CERT_FILE" "$IRONIC_CACERT_FILE"
    fi
else
    export IRONIC_TLS_SETUP="false"
    export IRONIC_SCHEME="http"
fi

if [[ -f "$IRONIC_VMEDIA_CERT_FILE" ]]; then
    export IRONIC_VMEDIA_TLS_SETUP="true"
else
    export IRONIC_VMEDIA_TLS_SETUP="false"
fi

if [[ -f "$IPXE_CERT_FILE" ]]; then
    export IPXE_SCHEME="https"
    export IPXE_TLS_SETUP="true"
else
    export IPXE_SCHEME="http"
    export IPXE_TLS_SETUP="false"
fi

if [[ -f "$MARIADB_CACERT_FILE" ]]; then
    export MARIADB_TLS_ENABLED="true"
else
    export MARIADB_TLS_ENABLED="false"
fi

configure_restart_on_certificate_update()
{
    local enabled="$1"
    local service="$2"
    local cert_file="$3"
    local signal="TERM"

    if [[ "${enabled}" == "true" ]] && [[ "${RESTART_CONTAINER_CERTIFICATE_UPDATED}" == "true" ]]; then
        if [[ "${service}" == httpd ]]; then
            # shellcheck disable=SC2034
            signal="WINCH"
        fi

        # Use watchmedo to monitor certificate file deletion
        # shellcheck disable=SC2016
        watchmedo shell-command \
            --patterns="$(basename "${cert_file}")" \
            --ignore-directories \
            --command='if [[ "${watch_event_type}" == "deleted" ]]; then pkill -'"${signal}"' '"${service}"'; fi' \
            "$(dirname "${cert_file}")" &
    fi
}

if ls "${BMC_CACERTS_PATH}"/* > /dev/null 2>&1; then
    export BMC_TLS_ENABLED="true"
    cat "${BMC_CACERTS_PATH}"/* > "${BMC_CACERT_FILE}"
else
    export BMC_TLS_ENABLED="false"
fi

if [ -f "${WEBSERVER_CACERT_FILE:-}" ]; then
    copy_atomic "${WEBSERVER_CACERT_FILE}" "${IPA_CACERT_FILE}"
elif [ -f "${DEFAULT_CACERT_BUNDLE}" ]; then
    copy_atomic "${DEFAULT_CACERT_BUNDLE}" "${IPA_CACERT_FILE}"
fi

if [ -f "${IRONIC_CACERT_FILE}" ]; then
    cat "${IRONIC_CACERT_FILE}" >> "${IPA_CACERT_FILE}"
fi

if ! openssl verify -CAfile "${IPA_CACERT_FILE}" "${IRONIC_CERT_FILE}" > /dev/null 2>&1; then
    # if we are unable to verify the Ironic cert file set IPA_INSECURE to true
    export IRONIC_IPA_INSECURE="1"
fi

generate_cacert_bundle_initrd()
(
    local output_path="$1"
    local temp_dir

    temp_dir="$(mktemp -d)"

    chmod 0755 "${temp_dir}" || return

    cd "${temp_dir}" || return

    mkdir -p etc/ironic-python-agent.d etc/ironic-python-agent
    cp "${IPA_CACERT_FILE}" etc/ironic-python-agent/ironic.crt
    cat > etc/ironic-python-agent.d/ironic-tls.conf <<EOF
[DEFAULT]
cafile = /etc/ironic-python-agent/ironic.crt
EOF

    find . | cpio -o -H newc -R +0:+0 --reproducible >> "${output_path}"

    # Remove temp directory
    cd && rm -rf "${temp_dir}"
)
