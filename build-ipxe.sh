#!/bin/bash

set -eux -o pipefail

dnf install -y gcc-aarch64-linux-gnu gcc-x86_64-linux-gnu

cd ipxe/src
# NOTE(elfosardo): warning should not be treated as errors by default
export NO_WERROR=1

CROSS_COMPILE=aarch64-linux-gnu- make bin-arm64-efi/snponly.efi
CROSS_COMPILE=x86_64-linux-gnu- make bin-x86_64-efi/snponly.efi
make bin/undionly.kpxe
