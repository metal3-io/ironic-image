#!/usr/bin/bash

set -euxo pipefail

git clone https://github.com/ipxe/ipxe.git
cd ipxe
mkdir out
git reset --hard "$IPXE_COMMIT_HASH"
cd src

# Build iPXE binaries based on architecture
if [[ "$TARGETARCH" == "amd64" ]]; then
    NO_WERROR=1 make bin/undionly.kpxe bin-x86_64-efi/snponly.efi
    NO_WERROR=1 make CROSS=aarch64-linux-gnu- bin-arm64-efi/snponly.efi
elif [[ "$TARGETARCH" == "arm64" ]]; then
    NO_WERROR=1 make bin-arm64-efi/snponly.efi
    NO_WERROR=1 make CROSS=x86_64-linux-gnu- bin/undionly.kpxe bin-x86_64-efi/snponly.efi
else
    echo "ERROR: Unsupported build architecture: $TARGETARCH"
    exit 1
fi

cp bin/undionly.kpxe ../out/
cp bin-x86_64-efi/snponly.efi ../out/snponly-x86_64.efi
cp bin-arm64-efi/snponly.efi ../out/snponly-arm64.efi
