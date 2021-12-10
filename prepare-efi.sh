#!/bin/bash

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
else
    echo "WARNING: don't know how to build an EFI image on $ARCH"
    touch "$DEST"
    exit 0
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
