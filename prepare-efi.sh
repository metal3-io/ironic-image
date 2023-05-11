#!/bin/bash

set -euxo pipefail

OS=${1:-centos}
DEST=${2:-/tmp/esp.img}
ARCH=$(uname -m)

if [[ "$ARCH" == "x86_64" ]]; then
    PACKAGES=grub2-efi-x64
    BOOTEFI=BOOTX64.EFI
    GRUBEFI=grubx64.efi
elif [[ "$ARCH" == "aarch64" ]]; then
    PACKAGES=grub2-efi-aa64
    BOOTEFI=BOOTAA64.EFI
    GRUBEFI=grubaa64.efi
else
    echo "WARNING: don't know how to build an EFI image on $ARCH"
    touch "$DEST"
    exit 0
fi

# NOTE(elfosardo): glibc-gconv-extra was included by default in the past and
# we need it otherwise mkfs.msdos will fail with:
# ``Cannot initialize conversion from codepage 850 to ANSI_X3.4-1968: Invalid argument``
# ``Cannot initialize conversion from ANSI_X3.4-1968 to codepage 850: Invalid argument``
# subsequently making mmd fail with:
# ``Error converting to codepage 850 Invalid argument``
# ``Cannot initialize '::'``
# This is due to the conversion table missing codepage 850, included in glibc-gconv-extra
# shellcheck disable=SC2086
dnf install -y grub2 shim dosfstools mtools glibc-gconv-extra $PACKAGES

## TODO(TheJulia): At some point we may want to try and make the size
## of the ESP image file to be sized smaller for the files that need to
## be copied in, however that requires more advanced scripting beyond
## an MVP.
dd bs=1024 count=6400 if=/dev/zero of="$DEST"
mkfs.msdos -F 12 -n 'ESP_IMAGE' "$DEST"

mmd -i "$DEST" EFI
mmd -i "$DEST" EFI/BOOT
mcopy -i "$DEST" -v "/boot/efi/EFI/BOOT/$BOOTEFI" ::EFI/BOOT
mcopy -i "$DEST" -v "/boot/efi/EFI/$OS/$GRUBEFI" ::EFI/BOOT
mdir -i "$DEST" ::EFI/BOOT
