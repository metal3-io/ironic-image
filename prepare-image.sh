#!/usr/bin/bash

set -ex

dnf upgrade -y
dnf --setopt=install_weak_deps=False install -y $(cat /tmp/main-packages-list.txt)
if [ $(uname -m) = "x86_64" ]; then
    dnf install -y syslinux-nonlinux;
fi
dnf clean all
rm -rf /var/cache/{yum,dnf}/*
