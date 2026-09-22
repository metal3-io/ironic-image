#!/usr/bin/bash

set -euxo pipefail

IPXE_ENABLE_IPV6="${IPXE_ENABLE_IPV6:-false}"
IPXE_ENABLE_TLS="${IPXE_ENABLE_TLS:-false}"

git clone https://github.com/ipxe/ipxe.git
cd ipxe
mkdir out
git reset --hard "$IPXE_COMMIT_HASH"
cd src

# Common make options for every arch build.
declare -a IPXE_MAKE_OPTS=("NO_WERROR=1")

# IPv6: config/general.h ships NET_PROTO_IPV6 commented out, uncomment it.
if [[ "${IPXE_ENABLE_IPV6}" == "true" ]]; then
    sed -i 's|^//#define\s*NET_PROTO_IPV6|#define NET_PROTO_IPV6|' config/general.h
fi

# TLS: enable HTTPS download proto and embed the cert(s).
if [[ "${IPXE_ENABLE_TLS}" == "true" ]]; then
    if [[ ! -r "${IPXE_CERT_FILE}" ]]; then
        echo "ERROR: TLS enabled but cert missing/unreadable: ${IPXE_CERT_FILE}" >&2
        exit 1
    fi
    # DOWNLOAD_PROTO_HTTPS ships as #undef, turn it on. HTTP left enabled.
    sed -i 's|^#undef\s*DOWNLOAD_PROTO_HTTPS|#define DOWNLOAD_PROTO_HTTPS|' config/general.h
    # Trust anchor for server verification.
    IPXE_MAKE_OPTS+=("TRUST=${IPXE_CERT_FILE}")
    # If a key is also present, embed a client cert for mutual TLS.
    if [[ -r "${IPXE_KEY_FILE}" ]]; then
        IPXE_MAKE_OPTS+=("CERT=${IPXE_CERT_FILE}" "PRIVKEY=${IPXE_KEY_FILE}")
    fi
fi

# Build iPXE binaries based on architecture
if [[ "$TARGETARCH" == "amd64" ]]; then
    make "${IPXE_MAKE_OPTS[@]}" bin/undionly.kpxe bin-x86_64-efi/snponly.efi
    make "${IPXE_MAKE_OPTS[@]}" CROSS=aarch64-linux-gnu- bin-arm64-efi/snponly.efi
elif [[ "$TARGETARCH" == "arm64" ]]; then
    make "${IPXE_MAKE_OPTS[@]}" bin-arm64-efi/snponly.efi
    make "${IPXE_MAKE_OPTS[@]}" CROSS=x86_64-linux-gnu- bin/undionly.kpxe bin-x86_64-efi/snponly.efi
else
    echo "ERROR: Unsupported build architecture: $TARGETARCH"
    exit 1
fi

cp bin/undionly.kpxe ../out/
cp bin-x86_64-efi/snponly.efi ../out/snponly-x86_64.efi
cp bin-arm64-efi/snponly.efi ../out/snponly-arm64.efi
