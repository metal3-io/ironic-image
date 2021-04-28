#!/usr/bin/bash

set -euxo pipefail

dnf install -y python3 python3-requests
curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python3 - -b master current-tripleo --no-stream
dnf upgrade -y
xargs -rtd'\n' dnf --setopt=install_weak_deps=False install -y < /tmp/${PKGS_LIST}
if [[ ! -z ${EXTRA_PKGS_LIST:-} ]]; then
    if [[ -s /tmp/${EXTRA_PKGS_LIST} ]]; then
        xargs -rtd'\n' dnf --setopt=install_weak_deps=False install -y < /tmp/${EXTRA_PKGS_LIST}
    fi
fi

dnf clean all
rm -rf /var/cache/{yum,dnf}/*
if [[ ! -z ${PATCH_LIST:-} ]]; then
    if [[ -s "/tmp/${PATCH_LIST}" ]]; then
        /bin/patch-image.sh;
    fi
fi
rm -f /bin/patch-image.sh

