#!/usr/bin/bash

set -euxo pipefail

IRONIC_PKG_LIST="/tmp/ironic-${INSTALL_TYPE}-list"

echo "install_weak_deps=False" >> /etc/dnf/dnf.conf
# Tell RPM to skip installing documentation
echo "tsflags=nodocs" >> /etc/dnf/dnf.conf

dnf install -y 'dnf-command(config-manager)'

# NOTE(elfosardo): building the container using ironic RPMs is
# now deprecated and it will be removed in the future.
# RPM install #
if [[ "$INSTALL_TYPE" == "rpm" ]]; then
    curl -o /etc/yum.repos.d/delorean.repo https://trunk.rdoproject.org/centos9-master/puppet-passed-ci/delorean.repo && \
    curl -o /etc/yum.repos.d/delorean-deps.repo https://trunk.rdoproject.org/centos9-master/delorean-deps.repo

    # NOTE(elfosardo): enable CRB repo for more python3 dependencies
    dnf config-manager --set-enabled crb
    dnf upgrade -y
    xargs -rtd'\n' dnf install -y < "$IRONIC_PKG_LIST"
fi

# SOURCE install #
if [[ "$INSTALL_TYPE" == "source" ]]; then
    # emulate uid/gid configuration to match rpm install
    BUILD_DEPS="python3-devel gcc git-core python3-setuptools python3-jinja2"
    dnf upgrade -y
    # NOTE(dtantsur): pip is a requirement of python3 in CentOS
    # shellcheck disable=SC2086
    dnf install -y python3-pip $BUILD_DEPS
    # NOTE(elfosardo): pinning pip and setuptools version to avoid
    # incompatibilities and errors during packages installation;
    # versions should be updated regularly, for example
    # after cutting a release branch.
    python3 -m pip install --no-cache-dir pip==24.1 setuptools==74.1.2

    IRONIC_PKG_LIST_FINAL="/tmp/ironic-${INSTALL_TYPE}-list-final"

    python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ, path=os.path))' < "${IRONIC_PKG_LIST}" > "${IRONIC_PKG_LIST_FINAL}"

    UPPER_CONSTRAINTS_PATH="/tmp/${UPPER_CONSTRAINTS_FILE:-}"

    # NOTE(elfosardo): if the content of the upper-constraints file is empty,
    # we give as assumed that we're on the master branch
    if [[ ! -f "${UPPER_CONSTRAINTS_PATH}" ]]; then
        UPPER_CONSTRAINTS_PATH="/tmp/upper-constraints.txt"
        curl -L https://releases.openstack.org/constraints/upper/master -o "${UPPER_CONSTRAINTS_PATH}"
    fi

    if [[ -n ${SUSHY_SOURCE:-} ]]; then
        sed -i '/^sushy===/d' "$UPPER_CONSTRAINTS_PATH"
    fi

    if [[ -n ${IRONIC_LIB_SOURCE:-} ]]; then
        sed -i '/^ironic-lib===/d' "$UPPER_CONSTRAINTS_PATH"
    fi

    python3 -m pip install --no-cache-dir --ignore-installed --prefix /usr -r "$IRONIC_PKG_LIST_FINAL" -c "${UPPER_CONSTRAINTS_PATH}"

    # ironic system configuration
    mkdir -p /var/log/ironic /var/lib/ironic
    getent group ironic > /dev/null || groupadd -r ironic
    getent passwd ironic > /dev/null || useradd -r -g ironic -s /sbin/nologin ironic -d /var/lib/ironic

    # clean installed build dependencies
    # shellcheck disable=SC2086
    dnf remove -y $BUILD_DEPS
fi

xargs -rtd'\n' dnf install -y < /tmp/"${PKGS_LIST}"

if [[ -n "${EXTRA_PKGS_LIST:-}" ]]; then
    if [[ -s "/tmp/${EXTRA_PKGS_LIST}" ]]; then
        xargs -rtd'\n' dnf install -y < /tmp/"${EXTRA_PKGS_LIST}"
    fi
fi

#dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
#dnf config-manager --set-disabled epel
#dnf install -y --enablerepo=epel inotify-tools
dnf install -y https://rpmfind.net/linux/fedora/linux/releases/40/Everything/x86_64/os/Packages/i/inotify-tools-3.22.1.0-7.fc40.x86_64.rpm

dnf remove -y --noautoremove 'dnf-command(config-manager)'

# NOTE(elfosardo): we need to reinstall tzdata as the base CS9 container removes
# its content, for more info see https://bugzilla.redhat.com/show_bug.cgi?id=2052861
dnf reinstall -y tzdata

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

dnf clean all
rm -rf /var/cache/{yum,dnf}/*
