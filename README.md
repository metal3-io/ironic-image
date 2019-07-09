Metal3 Ironic Container
=======================

This repo contains the files needed to build the Ironic images used by Metal3.

When updated, builds are automatically triggered on https://quay.io/repository/metal3-io/ironic/

This repo supports the creation of multiple containers needed when provisioning baremetal nodes with Ironic. Eventually there will be separate images for each container, but currently separate containers can share this same image with specific entry points.

The following entry points are provided:
- runironic - Starts the ironic-conductor and ironic-api processes to manage the provisioning of baremetal nodes.  Details on Ironic can be found at https://docs.openstack.org/ironic/latest/.  This is the default entry point used by the Dockerfile.
- rundnsmasq - Runs the dnmasq dhcp server to provide addresses and initiate PXE boot of baremetal nodes.  This includes a lightweight TFTP server.  Details on dnsmasq can be found at http://www.thekelleys.org.uk/dnsmasq/doc.html.
- runhttpd - Starts the Apache web server to provide images via http for PXE boot and for deployment of the final images.
- runmariadb - Provides a database to store information associated with baremetal nodes.

All of the containers must share a common mount point or data store.  Ironic requires files for both the TFTP server and HTTP server to be stored in the same partition.  This common store must include, in <shared store>/html/images, the following images:
- ironic-python-agent.kernel
- ironic-python-agent.initramfs
- final image to be deployed onto node in qcow2 format

All of the containers also store log files to <shared store>/log/.

The following environment variables can be passed in to customize run-time functionality:
- PROVISIONING_INTERFACE - interface to use for ironic, dnsmasq(dhcpd) and httpd (default provisioning)
- DNSMASQ_EXCEPT_INTERFACE - interfaces to exclude when providing DHCP address (default "lo")
- HTTP_PORT - port used by http server (default 80)
- DHCP_RANGE - dhcp range to use for provisioning (default 172.22.0.10-172.22.0.100)
- MARIADB_PASSWORD - The database password
