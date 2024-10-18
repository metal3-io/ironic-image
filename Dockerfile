ARG BASE_IMAGE=quay.io/centos-bootc/centos-bootc:stream10

## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.

FROM $BASE_IMAGE AS ironic-builder

ARG IPXE_COMMIT_HASH=e965f179e1654103eca33feed7a9cc4c51d91be6

RUN dnf install -y gcc git make xz-devel

WORKDIR /tmp

RUN git clone https://github.com/ipxe/ipxe.git && \
      cd ipxe && \
      git reset --hard $IPXE_COMMIT_HASH && \
      cd src && \
      ARCH=$(uname -m | sed 's/aarch/arm/') && \
      # NOTE(elfosardo): warning should not be treated as errors by default
      NO_WERROR=1 make bin/undionly.kpxe "bin-$ARCH-efi/snponly.efi" && \
      ls -la

COPY prepare-efi.sh /bin/
RUN prepare-efi.sh centos

FROM $BASE_IMAGE

ENV PKGS_LIST=main-packages-list.txt
ARG EXTRA_PKGS_LIST
ARG PATCH_LIST
ARG INSTALL_TYPE=source

# build arguments for source build customization
ARG UPPER_CONSTRAINTS_FILE
ARG IRONIC_SOURCE
ARG IRONIC_LIB_SOURCE
ARG SUSHY_SOURCE

COPY sources /sources/

COPY ${UPPER_CONSTRAINTS_FILE} ironic-${INSTALL_TYPE}-list ${PKGS_LIST} ${EXTRA_PKGS_LIST:-$PKGS_LIST} ${PATCH_LIST:-$PKGS_LIST} /tmp/
COPY prepare-image.sh patch-image.sh configure-nonroot.sh /bin/

RUN prepare-image.sh && \
  rm -f /bin/prepare-image.sh

COPY scripts/ /bin/

# IRONIC #
COPY --from=ironic-builder /tmp/ipxe/src/bin/undionly.kpxe /tmp/ipxe/src/bin-x86_64-efi/snponly.efi /tftpboot/
COPY --from=ironic-builder /tmp/esp.img /tmp/uefi_esp.img

COPY ironic-config/ironic.conf.j2 /etc/ironic/
COPY ironic-config/inspector.ipxe.j2 ironic-config/httpd-ironic-api.conf.j2 ironic-config/ipxe_config.template /tmp/

# DNSMASQ
COPY ironic-config/dnsmasq.conf.j2 /etc/

# Custom httpd config, removes all but the bare minimum needed modules
COPY ironic-config/httpd.conf.j2 /etc/httpd/conf/
COPY ironic-config/httpd-modules.conf /etc/httpd/conf.modules.d/
COPY ironic-config/apache2-vmedia.conf.j2 /etc/httpd-vmedia.conf.j2
COPY ironic-config/apache2-ipxe.conf.j2 /etc/httpd-ipxe.conf.j2

# DATABASE
RUN mkdir -p /var/lib/ironic && \
  sqlite3 /var/lib/ironic/ironic.sqlite "pragma journal_mode=wal" && \
  dnf remove -y sqlite

# configure non-root user and set relevant permissions
RUN configure-nonroot.sh && \
  rm -f /bin/configure-nonroot.sh
