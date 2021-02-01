## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.

ARG OVERRIDE_DOCKER_IO_REGISTRY=${OVERRIDE_DOCKER_IO_REGISTRY:-"docker.io"}

FROM "${OVERRIDE_DOCKER_IO_REGISTRY}/"centos:centos7 AS builder
RUN yum install -y gcc git make genisoimage xz-devel grub2 grub2-efi-x64-modules shim dosfstools mtools

WORKDIR /tmp
COPY . .
RUN git clone https://github.com/ipxe/ipxe.git && \
      cd ipxe && \
      git checkout 3fe683ebab29afacf224e6b0921f6329bebcdca7 && \
      cd src && \
      sed -i -e "s/#undef.*NET_PROTO_IPV6/#define NET_PROTO_IPV6/g" config/general.h && \
      make bin/undionly.kpxe bin-x86_64-efi/ipxe.efi bin-x86_64-efi/snponly.efi

## TODO(TheJulia): At some point we may want to try and make the size
## of the ESP image file to be sized smaller for the files that need to
## be copied in, however that requires more advanced scripting beyond
## an MVP.
RUN if [ $(uname -m) = "x86_64" ]; then \
      dnf install -y genisoimage grub2 grub2-efi-x64 shim dosfstools mtools && \
      dd bs=1024 count=3200 if=/dev/zero of=esp.img && \
      mkfs.msdos -F 12 -n 'ESP_IMAGE' ./esp.img && \
      mmd -i esp.img EFI && \
      mmd -i esp.img EFI/BOOT && \
      mcopy -i esp.img -v /boot/efi/EFI/BOOT/BOOTX64.EFI ::EFI/BOOT && \
      mcopy -i esp.img -v /boot/efi/EFI/centos/grubx64.efi ::EFI/BOOT && \
      mdir -i esp.img ::EFI/BOOT; \
    else \
      touch /tmp/esp.img; \
    fi

FROM docker.io/centos:centos8

ENV PKGS_LIST=main-packages-list.txt
ARG EXTRA_PKGS_LIST
ARG PATCH_LIST

COPY ${PKGS_LIST} ${EXTRA_PKGS_LIST} ${PATCH_LIST} /tmp/
COPY prepare-image.sh patch-image.sh /bin/

RUN prepare-image.sh && \
  rm -f /bin/prepare-image.sh

COPY --from=builder /tmp/ipxe/src/bin/undionly.kpxe /tmp/ipxe/src/bin-x86_64-efi/snponly.efi /tmp/ipxe/src/bin-x86_64-efi/ipxe.efi /tftpboot/

COPY --from=builder /tmp/esp.img /tmp/uefi_esp.img

COPY config/ironic.conf.j2 /etc/ironic/

# TODO(dtantsur): remove scripts/runironic script when we stop supporting
# running both API and conductor processes via one entry point.
COPY scripts/ /bin/
COPY config/dnsmasq.conf.j2 /etc/
COPY config/inspector.ipxe.j2 config/dualboot.ipxe /tmp/

# Custom httpd config, removes all but the bare minimum needed modules
RUN rm -f /etc/httpd/conf.d/autoindex.conf /etc/httpd/conf.d/welcome.conf /etc/httpd/conf.modules.d/*.conf
COPY config/httpd.conf /etc/httpd/conf.d/
COPY config/httpd-modules.conf /etc/httpd/conf.modules.d/

ENTRYPOINT ["/bin/runironic"]
