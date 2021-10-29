ARG BASE_IMAGE=quay.io/centos/centos:stream8

## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.

FROM $BASE_IMAGE AS ironic-builder

RUN dnf install -y gcc git make xz-devel
WORKDIR /tmp
RUN git clone --depth 1 --branch v1.21.1 https://github.com/ipxe/ipxe.git && \
      cd ipxe && \
      cd src && \
      make bin/undionly.kpxe bin-x86_64-efi/ipxe.efi bin-x86_64-efi/snponly.efi

## TODO(TheJulia): At some point we may want to try and make the size
## of the ESP image file to be sized smaller for the files that need to
## be copied in, however that requires more advanced scripting beyond
## an MVP.
RUN if [ $(uname -m) = "x86_64" ]; then \
      dnf install -y genisoimage grub2 grub2-efi-x64 shim dosfstools mtools && \
      dd bs=1024 count=6400 if=/dev/zero of=esp.img && \
      mkfs.msdos -F 12 -n 'ESP_IMAGE' ./esp.img && \
      mmd -i esp.img EFI && \
      mmd -i esp.img EFI/BOOT && \
      mcopy -i esp.img -v /boot/efi/EFI/BOOT/BOOTX64.EFI ::EFI/BOOT && \
      mcopy -i esp.img -v /boot/efi/EFI/centos/grubx64.efi ::EFI/BOOT && \
      mdir -i esp.img ::EFI/BOOT; \
    else \
      touch /tmp/esp.img; \
    fi

FROM $BASE_IMAGE

ENV PKGS_LIST=main-packages-list.txt
ARG EXTRA_PKGS_LIST
ARG PATCH_LIST

COPY ${PKGS_LIST} ${EXTRA_PKGS_LIST:-$PKGS_LIST} ${PATCH_LIST:-$PKGS_LIST} /tmp/
COPY prepare-image.sh patch-image.sh /bin/

RUN prepare-image.sh && \
  rm -f /bin/prepare-image.sh


COPY scripts/ /bin/

# IRONIC #
RUN chown ironic:ironic /var/log/ironic && \
  # This file is generated after installing mod_ssl and it affects our configuration
  rm -f /etc/httpd/conf.d/ssl.conf

COPY --from=ironic-builder /tmp/ipxe/src/bin/undionly.kpxe /tmp/ipxe/src/bin-x86_64-efi/snponly.efi /tmp/ipxe/src/bin-x86_64-efi/ipxe.efi /tftpboot/
COPY --from=ironic-builder /tmp/esp.img /tmp/uefi_esp.img

COPY ironic-config/ironic.conf.j2 /etc/ironic/
COPY ironic-config/dnsmasq.conf.j2 /etc/
COPY ironic-config/inspector.ipxe.j2 ironic-config/dualboot.ipxe ironic-config/ironic-python-agent.ign.j2 /tmp/

# Custom httpd config, removes all but the bare minimum needed modules
RUN rm -f /etc/httpd/conf.d/autoindex.conf /etc/httpd/conf.d/welcome.conf /etc/httpd/conf.modules.d/*.conf
COPY ironic-config/httpd.conf /etc/httpd/conf.d/
COPY ironic-config/httpd-modules.conf /etc/httpd/conf.modules.d/
COPY ironic-config/apache2-ironic-api.conf.j2 /etc/httpd-ironic-api.conf.j2
COPY ironic-config/apache2-vmedia.conf.j2 /etc/httpd-vmedia.conf.j2

# IRONIC-INSPECTOR #
RUN mkdir -p /var/lib/ironic-inspector && \
  sqlite3 /var/lib/ironic-inspector/ironic-inspector.db "pragma journal_mode=wal" && \
  dnf remove -y sqlite

COPY ironic-inspector-config/ironic-inspector.conf.j2 /etc/ironic-inspector/
COPY ironic-inspector-config/inspector-apache.conf.j2 /etc/httpd/conf.d/
RUN rm -f /etc/httpd/conf.d/ssl.conf
