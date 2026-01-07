ARG BASE_IMAGE=quay.io/centos/centos:stream9

## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.

FROM $BASE_IMAGE AS ironic-builder

ARG IPXE_COMMIT_HASH=e965f179e1654103eca33feed7a9cc4c51d91be6
ARG TARGETARCH

WORKDIR /tmp

COPY prepare-ipxe.sh /bin/
RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked \ 
  prepare-ipxe.sh

COPY build-ipxe.sh /bin/
RUN build-ipxe.sh

COPY prepare-efi.sh /bin/
RUN prepare-efi.sh centos

# build actual image
FROM $BASE_IMAGE

# image.version will be set by automation during build
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Container image to run OpenStack Ironic as part of Metal³"
LABEL org.opencontainers.image.documentation="https://book.metal3.io/ironic/introduction"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 Ironic Container"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/ironic-image"
LABEL org.opencontainers.image.vendor="Metal3-io"

ARG TARGETARCH

ARG PKGS_LIST=main-packages-list.txt
ARG ARCH_PKGS_LIST=main-packages-list-${TARGETARCH}.txt
ARG EXTRA_PKGS_LIST
ARG PATCH_LIST

# build arguments for source build customization
ARG UPPER_CONSTRAINTS_FILE=upper-constraints.txt
ARG IRONIC_SOURCE=c2b5580b752bfa45cfa398c81fb1a305fe35464c # master
ARG SUSHY_SOURCE

COPY sources /sources/
COPY ${UPPER_CONSTRAINTS_FILE} ironic-packages-list ${PKGS_LIST} ${ARCH_PKGS_LIST} \
     ${EXTRA_PKGS_LIST:-$PKGS_LIST} ${PATCH_LIST:-$PKGS_LIST} \
     /tmp/
COPY ironic-config/inspector.ipxe.j2 ironic-config/httpd-ironic-api.conf.j2 \
     ironic-config/ipxe_config.template ironic-config/dnsmasq.conf.j2 \
     /templates/
COPY prepare-image.sh patch-image.sh configure-nonroot.sh /bin/
COPY scripts/ /bin/

RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked \
    prepare-image.sh && \
     rm -f /bin/prepare-image.sh

# IRONIC #
COPY --from=ironic-builder /tmp/ipxe/out/ /tftpboot/
COPY --from=ironic-builder /tmp/uefi_esp*.img /templates/

COPY ironic-config/ironic.conf.j2 /etc/ironic/

# Custom httpd config, removes all but the bare minimum needed modules
COPY ironic-config/httpd.conf.j2 /etc/httpd/conf/
COPY ironic-config/httpd-modules.conf /etc/httpd/conf.modules.d/
COPY ironic-config/apache2-vmedia.conf.j2 /templates/httpd-vmedia.conf.j2
COPY ironic-config/apache2-ipxe.conf.j2 /templates/httpd-ipxe.conf.j2

# DATABASE
RUN mkdir -p /var/lib/ironic && \
     sqlite3 /var/lib/ironic/ironic.sqlite "pragma journal_mode=wal" && \
     dnf remove -y sqlite && \
     dnf clean all && \
     rm -rf /var/cache/{yum,dnf}/*

# configure non-root user and set relevant permissions
RUN configure-nonroot.sh && rm -f /bin/configure-nonroot.sh
