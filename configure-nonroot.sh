#!/usr/bin/bash

# This script changes permissions to allow Ironic container to run as non-root
# user. As the same image is used to run ironic, ironic-httpd, ironic-dsnmasq,
# ironic-inspector and ironic-log-watch via BMO's ironic k8s manifest, it has
# to be configured to work with multiple different users and groups, while they
# share files via bind mounts (/shared, /certs/*), which can only get one
# group id as "fsGroup". Additionally, dnsmasq needs three capabilities to run
# which we provide via "setcap", and "allowPrivilegeEscalation: true" in
# manifest.

# do not merge - test

set -eux

# user and group are from ironic rpms (uid 997, gid 994)
IRONIC_USER="ironic"
IRONIC_GROUP="ironic"
INSPECTOR_GROUP="ironic-inspector"

# most containers mount /shared but dnsmasq can live without it
mkdir -p /shared
chown "${IRONIC_USER}":"${INSPECTOR_GROUP}" /shared

# we'll bind mount shared ca and ironic/inspector certificate dirs here
# that need to have correct ownership as the entire ironic in BMO
# deployment shares a single fsGroup in manifest's securityContext
mkdir -p /certs/ca
chown "${IRONIC_USER}":"${INSPECTOR_GROUP}" /certs{,/ca}
chmod 2775 /certs{,/ca}

# ironic, inspector and httpd related changes
chown -R root:"${IRONIC_GROUP}" /etc/ironic /etc/httpd/conf /etc/httpd/conf.d
chown -R "${IRONIC_USER}":"${INSPECTOR_GROUP}" /etc/ironic-inspector
chmod 2775 /etc/ironic /etc/ironic-inspector /etc/httpd/conf /etc/httpd/conf.d
chmod 664 /etc/ironic/* /etc/ironic-inspector/* /etc/httpd/conf/* /etc/httpd/conf.d/*

chown -R root:"${IRONIC_GROUP}" /var/lib/ironic
chown -R root:"${INSPECTOR_GROUP}" /var/lib/ironic-inspector
chmod 2775 /var/lib/ironic /var/lib/ironic-inspector
chmod 664 /var/lib/ironic/ironic.db /var/lib/ironic-inspector/ironic-inspector.db

# dnsmasq, and the capabilities required to run it as non-root user
chown -R root:"${IRONIC_GROUP}" /etc/dnsmasq.conf /var/lib/dnsmasq
chmod 2775 /var/lib/dnsmasq
touch /var/lib/dnsmasq/dnsmasq.leases
chmod 664 /etc/dnsmasq.conf /var/lib/dnsmasq/dnsmasq.leases

setcap "cap_net_raw,cap_net_admin,cap_net_bind_service=+eip" /usr/sbin/dnsmasq
