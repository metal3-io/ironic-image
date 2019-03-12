#!/bin/bash

set -xe

# Configure dnsmasq and pxe boot parameters.

IRONIC_IP=${IRONIC_IP:-"172.22.0.1"}
IRONIC_DHCP_RANGE=${IRONIC_DHCP_RANGE:-"172.22.0.10,172.22.0.100"}

cat /config/dnsmasq.conf | sed -e s/IRONIC_IP/$IRONIC_IP/g -e s/IRONIC_DHCP_RANGE/$IRONIC_DHCP_RANGE/g > /etc/dnsmasq.conf
cat /config/dualboot.ipxe | sed s/IRONIC_IP/$IRONIC_IP/g > /var/www/html/dualboot.ipxe
cat /config/inspector.ipxe | sed s/IRONIC_IP/$IRONIC_IP/g > /var/www/html/inspector.ipxe

# Add firewall rules to ensure the IPA ramdisk can reach Ironic and Inspector APIs on the host
# I suspect for kubernetes we can just use hostPort with hostNetwork.
for port in 5050 6385 ; do
    if ! iptables -C INPUT -i provisioning -p tcp -m tcp --dport $port -j ACCEPT > /dev/null 2>&1; then
        iptables -I INPUT -i provisioning -p tcp -m tcp --dport $port -j ACCEPT
    fi
done

# Get the images we need to serve.
mkdir -p /var/www/html/images
pushd /var/www/html/images

export RHCOS_IMAGE_URL=${RHCOS_IMAGE_URL:-"https://releases-rhcos.svc.ci.openshift.org/storage/releases/maipo/"}
export RHCOS_IMAGE_VERSION="${RHCOS_IMAGE_VERSION:-47.284}"
export RHCOS_IMAGE_NAME="redhat-coreos-maipo-${RHCOS_IMAGE_VERSION}"
export RHCOS_IMAGE_FILENAME="${RHCOS_IMAGE_NAME}-qemu.qcow2"
export RHCOS_IMAGE_FILENAME_OPENSTACK="${RHCOS_IMAGE_NAME}-openstack.qcow2"

# This is the one we actually want to use, but I'm not going to assemble it here
# in a kubernetes managed container.
export RHCOS_IMAGE_FILENAME_DUALDHCP="${RHCOS_IMAGE_NAME}-dualdhcp.qcow2"
export RHCOS_IMAGE_FILENAME_LATEST="redhat-coreos-maipo-latest.qcow2"

curl --insecure --compressed -L -o "${RHCOS_IMAGE_FILENAME_OPENSTACK}" "${RHCOS_IMAGE_URL}/${RHCOS_IMAGE_VERSION}/${RHCOS_IMAGE_FILENAME_OPENSTACK}".gz
curl --insecure --compressed -L https://images.rdoproject.org/master/rdo_trunk/current-tripleo/ironic-python-agent.tar | tar -xf -

if [ ! -e "$RHCOS_IMAGE_FILENAME_OPENSTACK.md5sum" -o \
     "$RHCOS_IMAGE_FILENAME_OPENSTACK" -nt "$RHCOS_IMAGE_FILENAME_OPENSTACK.md5sum" ] ; then
    md5sum "$RHCOS_IMAGE_FILENAME_OPENSTACK" | cut -f 1 -d " " > "$RHCOS_IMAGE_FILENAME_OPENSTACK.md5sum"
fi

ln -sf "$RHCOS_IMAGE_FILENAME_OPENSTACK" "$RHCOS_IMAGE_FILENAME_LATEST"
ln -sf "$RHCOS_IMAGE_FILENAME_OPENSTACK.md5sum" "$RHCOS_IMAGE_FILENAME_LATEST.md5sum"
popd

