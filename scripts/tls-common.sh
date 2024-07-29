#!/bin/bash

export IRONIC_CERT_FILE=/certs/ironic/tls.crt
export IRONIC_KEY_FILE=/certs/ironic/tls.key
export IRONIC_CACERT_FILE=/certs/ca/ironic/tls.crt
export IRONIC_INSECURE=${IRONIC_INSECURE:-false}
export IRONIC_SSL_PROTOCOL=${IRONIC_SSL_PROTOCOL:-"-ALL +TLSv1.2 +TLSv1.3"}
export IPXE_SSL_PROTOCOL=${IPXE_SSL_PROTOCOL:-"-ALL +TLSv1.2 +TLSv1.3"}
export IRONIC_VMEDIA_SSL_PROTOCOL=${IRONIC_VMEDIA_SSL_PROTOCOL:-"ALL"}

export IRONIC_VMEDIA_CERT_FILE=/certs/vmedia/tls.crt
export IRONIC_VMEDIA_KEY_FILE=/certs/vmedia/tls.key

export IPXE_CERT_FILE=/certs/ipxe/tls.crt
export IPXE_KEY_FILE=/certs/ipxe/tls.key

export RESTART_CONTAINER_CERTIFICATE_UPDATED=${RESTART_CONTAINER_CERTIFICATE_UPDATED:-"false"}

export MARIADB_CACERT_FILE=/certs/ca/mariadb/tls.crt

export IPXE_TLS_PORT="${IPXE_TLS_PORT:-8084}"

mkdir -p /certs/ironic
mkdir -p /certs/ca/ironic
mkdir -p /certs/ipxe
mkdir -p /certs/vmedia

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
