ARG BASE_IMAGE=quay.io/centos/centos:stream9-minimal

# Python tooling versions - update these regularly
ARG PIP_VERSION=26.0.1
ARG SETUPTOOLS_VERSION=80.10.2

## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.

FROM $BASE_IMAGE AS ironic-builder

ARG IPXE_COMMIT_HASH=d0ea2b1bb8f78b219f74424d435b92ff8aa0ea8d
ARG TARGETARCH

WORKDIR /tmp

COPY prepare-ipxe.sh /bin/
RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked \ 
  prepare-ipxe.sh

COPY build-ipxe.sh /bin/
RUN build-ipxe.sh

COPY prepare-efi.sh /bin/
RUN prepare-efi.sh centos

## Build Python wheels for dependencies
FROM $BASE_IMAGE AS deps-wheel-builder

ARG UPPER_CONSTRAINTS_FILE=upper-constraints.txt
ARG PIP_VERSION
ARG SETUPTOOLS_VERSION

ENV UPPER_CONSTRAINTS_FILE=${UPPER_CONSTRAINTS_FILE} \
    PIP_VERSION=${PIP_VERSION} \
    SETUPTOOLS_VERSION=${SETUPTOOLS_VERSION}

RUN --mount=type=cache,sharing=locked,target=/var/cache/dnf \
    echo "install_weak_deps=False" >> /etc/dnf/dnf.conf && \
    echo "tsflags=nodocs" >> /etc/dnf/dnf.conf && \
    echo "keepcache=1" >> /etc/dnf/dnf.conf && \
    microdnf install -y \
        gcc \
        python3.12-devel \
        python3.12-pip \
        python3.12-setuptools

COPY ${UPPER_CONSTRAINTS_FILE} ironic-deps-list /tmp/
COPY build-wheels.sh /bin/

RUN IRONIC_PKG_LIST=/tmp/ironic-deps-list /bin/build-wheels.sh

## Build Ironic and Sushy wheels
FROM $BASE_IMAGE AS ironic-wheel-builder

ARG UPPER_CONSTRAINTS_FILE=upper-constraints.txt
ARG IRONIC_SOURCE=79669b5de7396d105e17cbb5e0941facf6f9fcf7 # bugfix/34.0
ARG SUSHY_SOURCE
ARG PIP_VERSION
ARG SETUPTOOLS_VERSION

ENV IRONIC_SOURCE=${IRONIC_SOURCE} \
    SUSHY_SOURCE=${SUSHY_SOURCE} \
    UPPER_CONSTRAINTS_FILE=${UPPER_CONSTRAINTS_FILE} \
    PIP_VERSION=${PIP_VERSION} \
    SETUPTOOLS_VERSION=${SETUPTOOLS_VERSION}

RUN --mount=type=cache,sharing=locked,target=/var/cache/dnf \
    echo "install_weak_deps=False" >> /etc/dnf/dnf.conf && \
    echo "tsflags=nodocs" >> /etc/dnf/dnf.conf && \
    echo "keepcache=1" >> /etc/dnf/dnf.conf && \
    microdnf install -y \
        gcc \
        git-core \
        python3.12-devel \
        python3.12-pip \
        python3.12-setuptools

COPY sources /sources/
COPY ${UPPER_CONSTRAINTS_FILE} ironic-packages-list /tmp/
COPY build-wheels.sh /bin/

RUN /bin/build-wheels.sh

# build actual image
FROM $BASE_IMAGE

# Re-declare ARGs for this stage
ARG PIP_VERSION
ARG SETUPTOOLS_VERSION
ENV PIP_VERSION=${PIP_VERSION} \
    SETUPTOOLS_VERSION=${SETUPTOOLS_VERSION}

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

COPY ${PKGS_LIST} ${ARCH_PKGS_LIST} ${EXTRA_PKGS_LIST:-$PKGS_LIST} ${PATCH_LIST:-$PKGS_LIST} /tmp/
COPY ironic-config/inspector.ipxe.j2 ironic-config/httpd-ironic-api.conf.j2 \
     ironic-config/ipxe_config.template ironic-config/dnsmasq.conf.j2 \
     /templates/
COPY prepare-image.sh patch-image.sh configure-nonroot.sh /bin/
COPY scripts/ /bin/

# Install Python packages from pre-built wheels (mounted from both wheel-builder stages)
RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked \
    --mount=from=deps-wheel-builder,source=/wheels,target=/deps-wheels \
    --mount=from=ironic-wheel-builder,source=/wheels,target=/ironic-wheels \
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
RUN <<EORUN
set -euxo pipefail
mkdir -p /var/lib/ironic
sqlite3 /var/lib/ironic/ironic.sqlite "pragma journal_mode=wal"
microdnf remove -y sqlite
microdnf clean all
rm -rf /var/cache/{yum,dnf}/*
EORUN

# configure non-root user and set relevant permissions
RUN <<EORUN
set -euxo pipefail
configure-nonroot.sh
rm -f /bin/configure-nonroot.sh
EORUN
