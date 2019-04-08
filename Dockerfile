FROM docker.io/centos:centos7

RUN yum install -y python-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/5609d2e3aee35578e914bcbfac92a46c759c0a31/tripleo_repos/main.py | python - current && \
    yum install -y openstack-ironic-api openstack-ironic-conductor crudini iproute dnsmasq httpd qemu-img-ev iscsi-initiator-utils parted gdisk ipxe-bootimgs psmisc sysvinit-tools mariadb-server python-PyMySQL python2-chardet && \
    yum clean all

RUN mkdir /tftpboot && \
    cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /tftpboot/

COPY ./runironic.sh /bin/runironic
COPY ./rundnsmasq.sh /bin/rundnsmasq
COPY ./runhttpd.sh /bin/runhttpd
COPY ./runmariadb.sh /bin/runmariadb
COPY ./runhealthcheck.sh /bin/runhealthcheck

COPY ./dnsmasq.conf /etc/dnsmasq.conf
COPY ./inspector.ipxe /tmp/inspector.ipxe
COPY ./dualboot.ipxe /tmp/dualboot.ipxe

ENTRYPOINT ["/bin/runironic"]
