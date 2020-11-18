#!/usr/bin/bash

set -ex

dnf install -y python3 python3-requests
curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python3 - -b master current-tripleo
dnf upgrade -y
dnf --setopt=install_weak_deps=False install -y $(cat /tmp/main-packages-list.txt)
dnf clean all
rm -rf /var/cache/{yum,dnf}/*
