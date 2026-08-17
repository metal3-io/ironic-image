#!/usr/bin/bash

set -euxo pipefail

IPXE_ENABLE_TLS="${IPXE_ENABLE_TLS:-false}"

git clone https://github.com/ipxe/ipxe.git
cd ipxe
mkdir out
git reset --hard "$IPXE_COMMIT_HASH"
cd src

# Common make options for every arch build.
declare -a IPXE_MAKE_OPTS=("NO_WERROR=1")

# NOTE: at the pinned iPXE commit, config/general.h already #defines both
# NET_PROTO_IPV6 and DOWNLOAD_PROTO_HTTPS at the top level; they are only
# #undef'd inside the BIOS-constrained block. The EFI binaries we build here
# therefore already include IPv6 and HTTPS with no general.h edits needed.

# TLS: embed the cert(s) so iPXE can verify the HTTPS server.
if [[ "$IPXE_ENABLE_TLS" == "true" ]]; then
    if [[ ! -r "$IPXE_CERT_FILE" ]]; then
        echo "ERROR: TLS enabled but cert missing/unreadable: $IPXE_CERT_FILE" >&2
        exit 1
    fi
    # Embed the cert as trust anchor AND as an actual certificate so iPXE can
    # build/verify the chain (TRUST alone only pins the fingerprint).
    IPXE_MAKE_OPTS+=("CERT=${IPXE_CERT_FILE}" "TRUST=${IPXE_CERT_FILE}")
    # If a key is also present, embed it for mutual TLS (client auth).
    if [[ -r "$IPXE_KEY_FILE" ]]; then
        IPXE_MAKE_OPTS+=("PRIVKEY=${IPXE_KEY_FILE}")
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
