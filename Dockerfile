ARG BASE_IMAGE=quay.io/centos/centos:stream9-minimal

# Python tooling versions - update these regularly
ARG PIP_VERSION=26.0.1
ARG SETUPTOOLS_VERSION=82.0.1

## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.

FROM $BASE_IMAGE AS ironic-builder

ARG IPXE_COMMIT_HASH=d0ea2b1bb8f78b219f74424d435b92ff8aa0ea8d
ARG TARGETARCH

WORKDIR /tmp

COPY prepare-ipxe.sh build-ipxe.sh prepare-efi.sh /bin/

RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked <<EORUN
set -euxo pipefail
prepare-ipxe.sh
build-ipxe.sh
prepare-efi.sh centos
EORUN

## Build Python wheels for dependencies
FROM $BASE_IMAGE AS deps-wheel-builder

ARG UPPER_CONSTRAINTS_FILE=upper-constraints.txt
ARG PIP_VERSION
ARG SETUPTOOLS_VERSION

ENV UPPER_CONSTRAINTS_FILE=${UPPER_CONSTRAINTS_FILE} \
    PIP_VERSION=${PIP_VERSION} \
    SETUPTOOLS_VERSION=${SETUPTOOLS_VERSION}

RUN --mount=type=cache,sharing=locked,target=/var/cache/dnf <<EORUN
set -euxo pipefail
rm -f /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-SIG-Extras /etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial-PQC
# Find keys; if the list is empty, fail the build immediately
KEYS=$(find /etc/pki/rpm-gpg/ -name "RPM-GPG-KEY-cento*")
if [ -z "$KEYS" ]; then echo "ERROR: No CentOS GPG keys found in /etc/pki/rpm-gpg/"; exit 1; fi
echo "$KEYS" | xargs rpm --import
printf "[main]\ngpgcheck=1\ninstall_weak_deps=0\ntsflags=nodocs\nkeepcache=1\n" > /etc/dnf/dnf.conf
microdnf install -y \
    gcc \
    python3.12-devel \
    python3.12-pip \
    python3.12-setuptools
EORUN

COPY ${UPPER_CONSTRAINTS_FILE} ironic-deps-list /tmp/
COPY build-wheels.sh /bin/

RUN IRONIC_PKG_LIST=/tmp/ironic-deps-list /bin/build-wheels.sh

## Build Ironic and Sushy wheels
FROM $BASE_IMAGE AS ironic-wheel-builder

ARG UPPER_CONSTRAINTS_FILE=upper-constraints.txt
ARG IRONIC_SOURCE=c17d7f5709bb9b3e872ec7755c27c9d765a6a712 # master
ARG SUSHY_SOURCE=a18eaf3aed8366027d3d2decfcdf6b2318c1c995 # temporary pin to HEAD of 2026.1 to pull an urgent fix
ARG NGS_SOURCE=053d1243535efc985766b7bdcbabe4954380190f # master
ARG INSTALL_NGS=true
ARG PIP_VERSION
ARG SETUPTOOLS_VERSION

ENV IRONIC_SOURCE=${IRONIC_SOURCE} \
    SUSHY_SOURCE=${SUSHY_SOURCE} \
    NGS_SOURCE=${NGS_SOURCE} \
    INSTALL_NGS=${INSTALL_NGS} \
    UPPER_CONSTRAINTS_FILE=${UPPER_CONSTRAINTS_FILE} \
    PIP_VERSION=${PIP_VERSION} \
    SETUPTOOLS_VERSION=${SETUPTOOLS_VERSION}

RUN --mount=type=cache,sharing=locked,target=/var/cache/dnf <<EORUN
set -euxo pipefail
rm -f /etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-SIG-Extras /etc/pki/rpm-gpg/RPM-GPG-KEY-centosofficial-PQC
# Find keys; if the list is empty, fail the build immediately
KEYS=$(find /etc/pki/rpm-gpg/ -name "RPM-GPG-KEY-cento*")
if [ -z "$KEYS" ]; then echo "ERROR: No CentOS GPG keys found in /etc/pki/rpm-gpg/"; exit 1; fi
echo "$KEYS" | xargs rpm --import
printf "[main]\ngpgcheck=1\ninstall_weak_deps=0\ntsflags=nodocs\nkeepcache=1\n" > /etc/dnf/dnf.conf
microdnf install -y \
    gcc \
    git-core \
    python3.12-devel \
    python3.12-pip \
    python3.12-setuptools
EORUN

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
COPY ironic-config/ /tmp/ironic-config/
COPY prepare-image.sh patch-image.sh configure-nonroot.sh scripts/ /bin/

# Install Python packages from pre-built wheels (mounted from both wheel-builder stages)
RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked \
    --mount=from=deps-wheel-builder,source=/wheels,target=/deps-wheels \
    --mount=from=ironic-wheel-builder,source=/wheels,target=/ironic-wheels \
    prepare-image.sh && \
     rm -f /bin/prepare-image.sh

# IRONIC #
COPY --from=ironic-builder /tmp/ipxe/out/ /tftpboot/
COPY --from=ironic-builder /tmp/uefi_esp*.img /templates/

# Database, ironic-config distribution, and non-root user configuration
# Config files are placed here (after prepare-image.sh) because it removes
# /etc/httpd/conf.modules.d/*.conf during package setup.
RUN <<EORUN
set -euxo pipefail
cp /tmp/ironic-config/inspector.ipxe.j2 /tmp/ironic-config/httpd-ironic-api.conf.j2 \
   /tmp/ironic-config/ipxe_config.template /tmp/ironic-config/dnsmasq.conf.j2 \
   /templates/
mkdir -p /etc/ironic
cp /tmp/ironic-config/ironic.conf.j2 /etc/ironic/
cp /tmp/ironic-config/ironic-networking.conf.j2 /etc/ironic/
cp /tmp/ironic-config/httpd.conf.j2 /etc/httpd/conf/
cp /tmp/ironic-config/httpd-modules.conf /etc/httpd/conf.modules.d/
cp /tmp/ironic-config/apache2-vmedia.conf.j2 /templates/httpd-vmedia.conf.j2
cp /tmp/ironic-config/apache2-ipxe.conf.j2 /templates/httpd-ipxe.conf.j2
rm -rf /tmp/ironic-config
mkdir -p /var/lib/ironic
sqlite3 /var/lib/ironic/ironic.sqlite "pragma journal_mode=wal"
microdnf remove -y sqlite
microdnf clean all
rm -rf /var/cache/{yum,dnf}/*
configure-nonroot.sh
rm -f /bin/configure-nonroot.sh
EORUN
