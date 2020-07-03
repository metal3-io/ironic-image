## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.
FROM docker.io/centos:centos8 AS builder
RUN yum install -y gcc git make genisoimage xz-devel grub2 grub2-efi-x64-modules shim dosfstools mtools
WORKDIR /tmp
COPY . .
RUN git clone http://git.ipxe.org/ipxe.git && \
      cd ipxe && \
      git checkout 3fe683ebab29afacf224e6b0921f6329bebcdca7 && \
      cd src && \
      sed -i -e "s/#undef.*NET_PROTO_IPV6/#define NET_PROTO_IPV6/g" config/general.h && \
      make bin/undionly.kpxe bin-x86_64-efi/ipxe.efi bin-x86_64-efi/snponly.efi

## TODO(TheJulia): At some point we may want to try and make the size
## of the ESP image file to be sized smaller for the files that need to
## be copied in, however that requires more advanced scripting beyond
## an MVP.
## NOTE(derekh): We need to build our own grub image because the one
## that gets installed by grub2-efi-x64 (/boot/efi/EFI/centos/grubx64.efi)
## looks for grub.cnf in /EFI/centos, ironic puts it in /boot/grub
RUN dd bs=1024 count=2880 if=/dev/zero of=esp.img && \
      mkfs.msdos -F 12 -n 'ESP_IMAGE' ./esp.img && \
      mmd -i esp.img EFI && \
      mmd -i esp.img EFI/BOOT && \
      grub2-mkimage -C xz -O x86_64-efi -p /boot/grub -o /tmp/grubx64.efi boot linux search normal configfile part_gpt btrfs ext2 fat iso9660 loopback test keystatus gfxmenu regexp probe efi_gop efi_uga all_video gfxterm font scsi echo read ls cat png jpeg halt reboot && \
      mcopy -i esp.img -v /boot/efi/EFI/BOOT/BOOTX64.EFI ::EFI/BOOT && \
      mcopy -i esp.img -v /tmp/grubx64.efi ::EFI/BOOT && \
      mdir -i esp.img ::EFI/BOOT

FROM docker.io/centos:centos8

RUN dnf install -y python3 python3-requests epel-release && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python3 - -b master current-tripleo && \
    dnf update -y && \
    dnf install -y python3-gunicorn openstack-ironic-api openstack-ironic-conductor crudini \
        iproute dnsmasq httpd qemu-img iscsi-initiator-utils parted gdisk psmisc \
        mariadb-server genisoimage python3-ironic-prometheus-exporter \
        python3-jinja2 python3-sushy-oem-idrac python3-ibmcclient mod_ssl python3-mod_wsgi \
        inotify-tools && \
    dnf clean all && \
    rm -rf /var/cache/{yum,dnf}/*

RUN mkdir -p /tftpboot
COPY --from=builder /tmp/ipxe/src/bin/undionly.kpxe /tftpboot
COPY --from=builder /tmp/ipxe/src/bin-x86_64-efi/snponly.efi /tftpboot
COPY --from=builder /tmp/ipxe/src/bin-x86_64-efi/ipxe.efi /tftpboot

COPY --from=builder /tmp/esp.img /tmp/uefi_esp.img

COPY ./ironic.conf /tmp/ironic.conf
RUN crudini --merge /etc/ironic/ironic.conf < /tmp/ironic.conf && \
    rm /tmp/ironic.conf && chown ironic:ironic /var/log/ironic && \
    rm /etc/httpd/conf.d/ssl.conf

COPY ./runironic-api.sh /bin/runironic-api
COPY ./runironic-conductor.sh /bin/runironic-conductor
COPY ./runironic-exporter.sh /bin/runironic-exporter
COPY ./rundnsmasq.sh /bin/rundnsmasq
COPY ./runhttpd.sh /bin/runhttpd
COPY ./runmariadb.sh /bin/runmariadb
COPY ./configure-ironic.sh /bin/configure-ironic.sh
COPY ./ironic-common.sh /bin/ironic-common.sh
COPY ./apache2-ironic.conf.j2 /etc/httpd-ironic.conf.j2

# TODO(dtantsur): remove this script when we stop supporting running both
# API and conductor processes via one entry point.
COPY ./runironic.sh /bin/runironic

COPY ./dnsmasq.conf.j2 /etc/dnsmasq.conf.j2
COPY ./inspector.ipxe /tmp/inspector.ipxe
COPY ./dualboot.ipxe /tmp/dualboot.ipxe

ENTRYPOINT ["/bin/runironic"]
