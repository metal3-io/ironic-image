#!/usr/bin/bash

set -euxo pipefail

echo "install_weak_deps=False" >> /etc/dnf/dnf.conf
# Tell RPM to skip installing documentation
echo "tsflags=nodocs" >> /etc/dnf/dnf.conf

dnf upgrade -y
xargs -rtd'\n' dnf install -y < /tmp/${PKGS_LIST}
if [ $(uname -m) = "x86_64" ]; then
    dnf install -y syslinux-nonlinux;
fi

if [[ -n "${EXTRA_PKGS_LIST:-}" ]]; then
    if [[ -s "/tmp/${EXTRA_PKGS_LIST}" ]]; then
        xargs -rtd'\n' dnf install -y < /tmp/"${EXTRA_PKGS_LIST}"
    fi
fi

### cachito magic works for OCP only
if  [[ -f /tmp/main-packages-list.ocp ]]; then

    REQS="${REMOTE_SOURCES_DIR}/requirements.cachito"

    ls -la "${REMOTE_SOURCES_DIR}/" # DEBUG

    # load cachito variables only if they're available
    if [[ -d "${REMOTE_SOURCES_DIR}/cachito-gomod-with-deps" ]]; then
        source "${REMOTE_SOURCES_DIR}/cachito-gomod-with-deps/cachito.env"
        REQS="${REMOTE_SOURCES_DIR}/cachito-gomod-with-deps/app/requirements.cachito"
    fi

    ### source install ###
    BUILD_DEPS="python3-devel gcc gcc-c++"

    dnf install -y python3-pip python3-setuptools $BUILD_DEPS

    # NOTE(elfosardo): --no-index is used to install the packages emulating
    # an isolated environment in CI. Do not use the option for downstream
    # builds.
    PIP_OPTIONS=""
    if [[ ! -d "${REMOTE_SOURCES_DIR}/cachito-gomod-with-deps" ]]; then
        PIP_OPTIONS="--no-index"
    fi
    python3 -m pip install $PIP_OPTIONS --prefix /usr -r "${REQS}"

    # ironic and ironic-inspector system configuration
    mkdir -p /var/log/ironic /var/log/ironic-inspector /var/lib/ironic /var/lib/ironic-inspector
    getent group ironic >/dev/null || groupadd -r ironic
    getent passwd ironic >/dev/null || useradd -r -g ironic -s /sbin/nologin ironic -d /var/lib/ironic
    getent group ironic-inspector >/dev/null || groupadd -r ironic-inspector
    getent passwd ironic-inspector >/dev/null || useradd -r -g ironic-inspector -s /sbin/nologin ironic-inspector -d /var/lib/ironic-inspector

    dnf remove -y $BUILD_DEPS

    if [[ -d "${REMOTE_SOURCES_DIR}/cachito-gomod-with-deps" ]]; then
        rm -rf $REMOTE_SOURCES_DIR
    fi

fi
###

chown ironic:ironic /var/log/ironic
# This file is generated after installing mod_ssl and it affects our configuration
rm -f /etc/httpd/conf.d/ssl.conf /etc/httpd/conf.d/autoindex.conf /etc/httpd/conf.d/welcome.conf /etc/httpd/conf.modules.d/*.conf

# RDO-provided configuration forces creating log files
rm -f /usr/share/ironic/ironic-dist.conf /etc/ironic-inspector/inspector-dist.conf

# add ironic and ironic-inspector to apache group
usermod -aG ironic apache
usermod -aG ironic-inspector apache

dnf clean all
rm -rf /var/cache/{yum,dnf}/*
