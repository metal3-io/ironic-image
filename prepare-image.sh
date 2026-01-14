#!/usr/bin/bash

set -euxo pipefail

cat >> /etc/dnf/dnf.conf<< EOF
install_weak_deps=False
tsflags=nodocs
keepcache=1
EOF

# emulate uid/gid configuration to match rpm install
IRONIC_UID=997
IRONIC_GID=994

microdnf upgrade -y

# NOTE(dtantsur): pip is a requirement of python3 in CentOS
# shadow-utils provides groupadd/useradd/usermod (not in cs10-minimal)
microdnf install -y python3.12-pip shadow-utils

# NOTE(elfosardo): pinning pip and setuptools version to avoid
# incompatibilities and errors during packages installation;
# versions should be updated regularly, for example
# after cutting a release branch.
python3.12 -m pip install --no-cache-dir pip=="${PIP_VERSION}" setuptools=="${SETUPTOOLS_VERSION}"

# Install from pre-built wheels (mounted from both wheel-builder stages)
# No compilation needed here - wheels are already built
# Combine wheels into single directory, deduplicating
mkdir -p /tmp/all-wheels
cp -n /deps-wheels/*.whl /tmp/all-wheels/ 2>/dev/null || true
cp -n /ironic-wheels/*.whl /tmp/all-wheels/ 2>/dev/null || true

python3.12 -m pip install \
    --no-cache-dir \
    --no-index \
    --find-links=/tmp/all-wheels \
    --ignore-installed \
    --prefix /usr \
    /tmp/all-wheels/*.whl

rm -rf /tmp/all-wheels

# ironic system configuration
mkdir -p /var/log/ironic /var/lib/ironic
getent group ironic > /dev/null || groupadd -r ironic -g "${IRONIC_GID}"
getent passwd ironic > /dev/null || useradd -r -g ironic -u "${IRONIC_UID}" -s /sbin/nologin ironic -d /var/lib/ironic

xargs -rtd'\n' microdnf install -y < /tmp/"${PKGS_LIST}"
if [[ -s "/tmp/${ARCH_PKGS_LIST}" ]]; then
    xargs -rtd'\n' microdnf install -y < /tmp/"${ARCH_PKGS_LIST}"
fi

if [[ -n "${EXTRA_PKGS_LIST:-}" ]]; then
    if [[ -s "/tmp/${EXTRA_PKGS_LIST}" ]]; then
        xargs -rtd'\n' microdnf install -y < /tmp/"${EXTRA_PKGS_LIST}"
    fi
fi

# NOTE(elfosardo): we need to reinstall tzdata as the base CS9 container removes
# its content, for more info see https://bugzilla.redhat.com/show_bug.cgi?id=2052861
microdnf reinstall -y tzdata

chown ironic:ironic /var/log/ironic
# This file is generated after installing mod_ssl and it affects our configuration
rm -f /etc/httpd/conf.d/ssl.conf /etc/httpd/conf.d/autoindex.conf /etc/httpd/conf.d/welcome.conf /etc/httpd/conf.modules.d/*.conf

# RDO-provided configuration forces creating log files
rm -f /usr/share/ironic/ironic-dist.conf

# add ironic to apache group
usermod -aG ironic apache

# apply patches if present #
if [[ -n "${PATCH_LIST:-}" ]]; then
    if [[ -s "/tmp/${PATCH_LIST}" ]]; then
        /bin/patch-image.sh
    fi
fi
rm -f /bin/patch-image.sh

microdnf clean all
rm -rf /var/cache/{yum,dnf}/*

mv /bin/ironic-probe.sh /bin/ironic-readiness
cp /bin/ironic-readiness /bin/ironic-liveness
mkdir /data /conf
