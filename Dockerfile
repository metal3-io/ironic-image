## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.
FROM docker.io/centos:centos8 AS builder
RUN yum install -y gcc git make genisoimage xz-devel grub2 grub2-efi-x64 grub2-efi-x64-modules shim-x64 dosfstools mtools
WORKDIR /tmp
COPY . .

## TODO(TheJulia): At some point we may want to try and make the size
## of the ESP image file to be sized smaller for the files that need to
## be copied in, however that requires more advanced scripting beyond
## an MVP.
RUN dd bs=1024 count=3840 if=/dev/zero of=esp.img && \
      mkfs.msdos -F 12 -n 'ESP_IMAGE' ./esp.img && \
      mmd -i esp.img EFI && \
      mmd -i esp.img EFI/BOOT && \
      mcopy -i esp.img -v /boot/efi/EFI/BOOT/BOOTX64.EFI ::EFI/BOOT && \
      mcopy -i esp.img -v /boot/efi/EFI/centos/grubx64.efi ::EFI/BOOT && \
      mdir -i esp.img ::EFI/BOOT

FROM docker.io/centos:centos8

RUN dnf install -y python3 python3-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python3 - -b master current && \
    dnf update -y && \
    dnf install -y python3-gunicorn openstack-ironic-api openstack-ironic-conductor crudini \
        iproute dnsmasq httpd qemu-img iscsi-initiator-utils parted gdisk psmisc \
        mariadb-server genisoimage python3-ironic-prometheus-exporter \
        python3-jinja2 python3-sushy-oem-idrac && \
    dnf clean all && \
    rm -rf /var/cache/{yum,dnf}/*

RUN mkdir -p /tftpboot/EFI/centos
COPY --from=builder /tmp/esp.img /tmp/uefi_esp.img
COPY --from=builder /boot/efi/EFI/BOOT/BOOTX64.EFI /tftpboot
COPY --from=builder boot/efi/EFI/centos/grubx64.efi /tftpboot

COPY ./ironic.conf /tmp/ironic.conf
COPY ./grub.cfg /tftpboot/EFI/centos/grub.cfg

RUN crudini --merge /etc/ironic/ironic.conf < /tmp/ironic.conf && \
    rm /tmp/ironic.conf

COPY ./runironic-api.sh /bin/runironic-api
COPY ./runironic-conductor.sh /bin/runironic-conductor
COPY ./runironic-exporter.sh /bin/runironic-exporter
COPY ./rundnsmasq.sh /bin/rundnsmasq
COPY ./runhttpd.sh /bin/runhttpd
COPY ./runmariadb.sh /bin/runmariadb
COPY ./configure-ironic.sh /bin/configure-ironic.sh
COPY ./ironic-common.sh /bin/ironic-common.sh

# TODO(dtantsur): remove this script when we stop supporting running both
# API and conductor processes via one entry point.
COPY ./runironic.sh /bin/runironic

COPY ./dnsmasq.conf.j2 /etc/dnsmasq.conf.j2

ENTRYPOINT ["/bin/runironic"]
