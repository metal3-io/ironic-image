ARG BASE_IMAGE=quay.io/centos/centos:stream8

## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.

FROM $BASE_IMAGE AS ironic-builder

# NOTE(elfosardo): glibc-gconv-extra was included by default in the past and
# we need it otherwise mkfs.msdos will fail with:
# ``Cannot initialize conversion from codepage 850 to ANSI_X3.4-1968: Invalid argument``
# ``Cannot initialize conversion from ANSI_X3.4-1968 to codepage 850: Invalid argument``
# subsequently making mmd fail with:
# ``Error converting to codepage 850 Invalid argument``
# ``Cannot initialize '::'``
# This is due to the conversion table missing codepage 850, included in glibc-gconv-extra
RUN dnf install -y gcc git make xz-devel glibc-gconv-extra
WORKDIR /tmp
RUN git clone --depth 1 --branch v1.21.1 https://github.com/ipxe/ipxe.git && \
      cd ipxe/src && \
      ARCH=$(uname -m | sed 's/aarch/arm/') && \
      make bin/undionly.kpxe bin-$ARCH-efi/ipxe.efi bin-$ARCH-efi/snponly.efi

COPY prepare-efi.sh /bin/
RUN prepare-efi.sh centos

FROM $BASE_IMAGE

ENV PKGS_LIST=main-packages-list.txt
ARG EXTRA_PKGS_LIST
ARG PATCH_LIST
ARG INSTALL_TYPE=rpm

COPY ironic-${INSTALL_TYPE}-list.txt ${PKGS_LIST} ${EXTRA_PKGS_LIST:-$PKGS_LIST} ${PATCH_LIST:-$PKGS_LIST} /tmp/
COPY prepare-image.sh patch-image.sh /bin/

RUN prepare-image.sh && \
  rm -f /bin/prepare-image.sh

COPY scripts/ /bin/

# IRONIC #
COPY --from=ironic-builder /tmp/ipxe/src/bin/undionly.kpxe /tmp/ipxe/src/bin-x86_64-efi/snponly.efi /tmp/ipxe/src/bin-x86_64-efi/ipxe.efi /tftpboot/
COPY --from=ironic-builder /tmp/esp.img /tmp/uefi_esp.img

COPY ironic-config/ironic.conf.j2 /etc/ironic/
COPY ironic-config/dnsmasq.conf.j2 /etc/
COPY ironic-config/inspector.ipxe.j2 ironic-config/ironic-python-agent.ign.j2 /tmp/

# Custom httpd config, removes all but the bare minimum needed modules
COPY ironic-config/httpd.conf /etc/httpd/conf.d/
COPY ironic-config/httpd-modules.conf /etc/httpd/conf.modules.d/
COPY ironic-config/apache2-ironic-api.conf.j2 /etc/httpd-ironic-api.conf.j2
COPY ironic-config/apache2-vmedia.conf.j2 /etc/httpd-vmedia.conf.j2

# IRONIC-INSPECTOR #
RUN mkdir -p /var/lib/ironic /var/lib/ironic-inspector && \
  sqlite3 /var/lib/ironic/ironic.db "pragma journal_mode=wal" && \
  sqlite3 /var/lib/ironic-inspector/ironic-inspector.db "pragma journal_mode=wal" && \
  dnf remove -y sqlite

COPY ironic-inspector-config/ironic-inspector.conf.j2 /etc/ironic-inspector/
COPY ironic-inspector-config/inspector-apache.conf.j2 /etc/httpd/conf.d/
