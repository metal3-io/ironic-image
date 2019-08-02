#!/bin/bash -x
mkdir /tftpboot
cp /usr/share/ipxe/undionly.kpxe /tftpboot/
if [ -f "/usr/share/ipxe/ipxe.efi" ]; then
    cp /usr/share/ipxe/ipxe.efi /tftpboot/ipxe.efi
elif [ -f "/usr/share/ipxe/ipxe-x86_64.efi" ]; then
    cp  /usr/share/ipxe/ipxe-x86_64.efi /tftpboot/ipxe.efi
else
    echo "Fatal Error - Failed to find ipxe binary"
    exit 1
fi

