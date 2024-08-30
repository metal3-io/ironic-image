#!/usr/bin/bash

# This script changes permissions to allow Ironic container to run as non-root
# user. As the same image is used to run ironic, ironic-httpd, ironic-dsnmasq,
# and ironic-log-watch via BMO's ironic k8s manifest, it has
# to be configured to work with multiple different users and groups, while they
# share files via bind mounts (/shared, /certs/*), which can only get one
# group id as "fsGroup". Additionally, dnsmasq needs three capabilities to run
# which we provide via "setcap", and "allowPrivilegeEscalation: true" in
# manifest.

set -eux

# user and group are from ironic rpms (uid 997, gid 994)
IRONIC_USER="ironic"
IRONIC_GROUP="ironic"

# most containers mount /shared but dnsmasq can live without it
mkdir -p /shared
chown "${IRONIC_USER}":"${IRONIC_GROUP}" /shared

# we'll bind mount shared ca and ironic certificate dirs here
# that need to have correct ownership as the entire ironic in BMO
# deployment shares a single fsGroup in manifest's securityContext
mkdir -p /certs/ca
chown "${IRONIC_USER}":"${IRONIC_GROUP}" /certs{,/ca}
chmod 2775 /certs{,/ca}

# ironic and httpd related changes
chown -R root:"${IRONIC_GROUP}" /etc/ironic /etc/httpd/conf /etc/httpd/conf.d
chmod 2775 /etc/ironic /etc/httpd/conf /etc/httpd/conf.d
chmod 664 /etc/ironic/* /etc/httpd/conf/* /etc/httpd/conf.d/*

chown -R root:"${IRONIC_GROUP}" /var/lib/ironic
chmod 2775 /var/lib/ironic
chmod 664 /var/lib/ironic/ironic.sqlite

# dnsmasq, and the capabilities required to run it as non-root user
chown -R root:"${IRONIC_GROUP}" /etc/dnsmasq.conf /var/lib/dnsmasq
chmod 2775 /var/lib/dnsmasq
touch /var/lib/dnsmasq/dnsmasq.leases
chmod 664 /etc/dnsmasq.conf /var/lib/dnsmasq/dnsmasq.leases

# probes that are created before start
touch /bin/ironic-{readi,live}ness
chown root:"${IRONIC_GROUP}" /bin/ironic-{readi,live}ness
chmod 775 /bin/ironic-{readi,live}ness

setcap "cap_net_raw,cap_net_admin,cap_net_bind_service=+eip" /usr/sbin/dnsmasq
