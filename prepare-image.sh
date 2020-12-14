#!/usr/bin/bash

set -euxo pipefail

dnf upgrade -y
xargs -rd'\n' dnf --setopt=install_weak_deps=False install -y < /tmp/${PKGS_LIST}
if [ $(uname -m) = "x86_64" ]; then
    dnf install -y syslinux-nonlinux;
fi
if [[ ! -z ${EXTRA_PKGS_LIST:-} ]]; then
    if [[ -s /tmp/${EXTRA_PKGS_LIST} ]]; then
        xargs -rd'\n' dnf --setopt=install_weak_deps=False install -y < /tmp/${EXTRA_PKGS_LIST}
    fi
fi
dnf clean all
rm -rf /var/cache/{yum,dnf}/*

