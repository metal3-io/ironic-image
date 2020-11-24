#!/usr/bin/bash

set -ex

dnf upgrade -y
dnf --setopt=install_weak_deps=False install -y $(cat /tmp/${PKGS_LIST})
if [ $(uname -m) = "x86_64" ]; then
    dnf install -y syslinux-nonlinux;
fi
if [[ ! -z ${EXTRA_PKGS_LIST} ]]; then
    if [[ -s /tmp/${EXTRA_PKGS_LIST} ]]; then
        dnf --setopt=install_weak_deps=False install -y $(cat /tmp/${EXTRA_PKGS_LIST})
    fi
fi
dnf clean all
rm -rf /var/cache/{yum,dnf}/*
