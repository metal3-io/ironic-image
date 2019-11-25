## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.
FROM docker.io/centos:centos7 AS builder
RUN yum install -y gcc git make genisoimage xz-devel
WORKDIR /tmp
COPY . .
RUN git clone http://git.ipxe.org/ipxe.git && \
      cd ipxe && \
      git checkout 3fe683ebab29afacf224e6b0921f6329bebcdca7 && \
      cd src && \
      sed -i -e "s/#undef.*NET_PROTO_IPV6/#define NET_PROTO_IPV6/g" config/general.h && \
      make bin/undionly.kpxe bin-x86_64-efi/ipxe.efi bin-x86_64-efi/snponly.efi

FROM docker.io/centos:centos7

RUN yum install -y python-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python - -b train current-tripleo && \
    yum update -y && \
    yum install -y python-gunicorn openstack-ironic-api openstack-ironic-conductor crudini \
        iproute dnsmasq httpd qemu-img-ev iscsi-initiator-utils parted gdisk psmisc \
        sysvinit-tools mariadb-server genisoimage python-ironic-prometheus-exporter && \
    yum clean all && \
    rm -rf /var/cache/{yum,dnf}/*

RUN mkdir -p /tftpboot
COPY --from=builder /tmp/ipxe/src/bin/undionly.kpxe /tftpboot
COPY --from=builder /tmp/ipxe/src/bin-x86_64-efi/snponly.efi /tftpboot
COPY --from=builder /tmp/ipxe/src/bin-x86_64-efi/ipxe.efi /tftpboot

COPY ./ironic.conf /tmp/ironic.conf
RUN crudini --merge /etc/ironic/ironic.conf < /tmp/ironic.conf && \
    rm /tmp/ironic.conf

COPY ./runironic-api.sh /bin/runironic-api
COPY ./runironic-conductor.sh /bin/runironic-conductor
COPY ./runironic-exporter.sh /bin/runironic-exporter
COPY ./rundnsmasq.sh /bin/rundnsmasq
COPY ./runhttpd.sh /bin/runhttpd
COPY ./runmariadb.sh /bin/runmariadb
COPY ./configure-ironic.sh /bin/configure-ironic.sh
COPY ./ironic-common.sh /bin/ironic-common.sh

# TODO(dtantsur): remove these 2 scripts if we decide to
# stop supporting running all 2 processes via one entry point.
COPY ./runhealthcheck.sh /bin/runhealthcheck
COPY ./runironic.sh /bin/runironic

COPY ./dnsmasq.conf.ipv4 /etc/dnsmasq.conf.ipv4
COPY ./dnsmasq.conf.ipv6 /etc/dnsmasq.conf.ipv6
COPY ./inspector.ipxe /tmp/inspector.ipxe
COPY ./dualboot.ipxe /tmp/dualboot.ipxe

ENTRYPOINT ["/bin/runironic"]
