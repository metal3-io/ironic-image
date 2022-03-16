#!/bin/bash

set -euxo pipefail

ARCH=$(uname -m)
DEST=${2:-/tmp/esp.img}
OS=${1:-centos}

if [ "$ARCH" = "x86_64" ]; then
    PACKAGES=grub2-efi-x64
    BOOTEFI=BOOTX64.EFI
    GRUBEFI=grubx64.efi
elif [ "$ARCH" = "aarch64" ]; then
    PACKAGES=grub2-efi-aa64
    BOOTEFI=BOOTAA64.EFI
    GRUBEFI=grubaa64.efi
    ARCH=arm64
else
    echo "WARNING: don't know how to build an EFI image on $ARCH"
    touch "$DEST"
    exit 0
fi

# NOTE(elfosardo) in CentOS distribution the packaged version of ipxe is too
# old for our needs, so we need to build it.
if [ "$OS" = "centos" ]; then
    # NOTE(elfosardo): glibc-gconv-extra was included by default in the past and
    # we need it otherwise mkfs.msdos will fail with:
    # ``Cannot initialize conversion from codepage 850 to ANSI_X3.4-1968: Invalid argument``
    # ``Cannot initialize conversion from ANSI_X3.4-1968 to codepage 850: Invalid argument``
    # subsequently making mmd fail with:
    # ``Error converting to codepage 850 Invalid argument``
    # ``Cannot initialize '::'``
    # This is due to the conversion table missing codepage 850, included in glibc-gconv-extra
    dnf install -y gcc git make xz-devel glibc-gconv-extra

    git clone --depth 1 --branch v1.21.1 https://github.com/ipxe/ipxe.git
    cd ipxe/src
    # NOTE(elfosardo): warning should not be treated as errors by default
    NO_WERROR=1 make bin/undionly.kpxe bin-$ARCH-efi/ipxe.efi bin-$ARCH-efi/snponly.efi
fi

dnf install -y grub2 shim dosfstools mtools $PACKAGES

## TODO(TheJulia): At some point we may want to try and make the size
## of the ESP image file to be sized smaller for the files that need to
## be copied in, however that requires more advanced scripting beyond
## an MVP.
dd bs=1024 count=6400 if=/dev/zero of=$DEST
mkfs.msdos -F 12 -n 'ESP_IMAGE' $DEST

mmd -i $DEST EFI
mmd -i $DEST EFI/BOOT
mcopy -i $DEST -v /boot/efi/EFI/BOOT/$BOOTEFI ::EFI/BOOT
mcopy -i $DEST -v /boot/efi/EFI/$OS/$GRUBEFI ::EFI/BOOT
mdir -i $DEST ::EFI/BOOT;
