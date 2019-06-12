FROM docker.io/centos:centos7

# TODO(iurygregory): remove epel-release and  other packages necessary for the ironic_prometheus_exporter when we have a package for it
RUN yum install -y python-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python - current-tripleo && \
    yum update -y && \
    yum install -y epel-release python-pip python-devel gcc openstack-ironic-api openstack-ironic-conductor crudini \
        iproute iptables dnsmasq httpd qemu-img-ev iscsi-initiator-utils parted gdisk ipxe-bootimgs psmisc sysvinit-tools \
        mariadb-server python-PyMySQL python2-chardet && \
    yum install -y python-configparser python2-prometheus_client && \
    yum clean all

RUN mkdir /tftpboot && \
    cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /tftpboot/

COPY ./installexporter.sh /bin/installexporter
RUN /bin/installexporter
COPY ./runironic.sh /bin/runironic
COPY ./rundnsmasq.sh /bin/rundnsmasq
COPY ./runhttpd.sh /bin/runhttpd
COPY ./runmariadb.sh /bin/runmariadb
COPY ./runhealthcheck.sh /bin/runhealthcheck
COPY ./runexporterapp.sh /bin/runexporterapp

COPY ./dnsmasq.conf /etc/dnsmasq.conf
COPY ./inspector.ipxe /tmp/inspector.ipxe
COPY ./dualboot.ipxe /tmp/dualboot.ipxe

ENTRYPOINT ["/bin/runironic"]
