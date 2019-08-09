FROM docker.io/centos:centos7

RUN yum install -y python-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python - -b stein current-tripleo && \
    yum update -y && \
    yum install -y iproute iptables dnsmasq httpd qemu-img-ev \
        iscsi-initiator-utils parted gdisk ipxe-bootimgs psmisc ipmitool \
        sysvinit-tools mariadb-server python-PyMySQL python2-chardet \
        python-babel python-debtcollector python-dateutil python-pyparsing \
        python-singledispatch python-futures \
        python-pip git gcc python-devel && \
    yum clean all

COPY ./actual-reqs.txt /var/tmp/actual-reqs.txt
COPY ./installer.sh /bin/installer.sh

RUN chmod +x /bin/installer.sh && /bin/installer.sh

RUN mkdir /tftpboot && \
    cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /tftpboot/

RUN mkdir -p /etc/ironic
COPY ./ironic.conf /tmp/ironic.conf
RUN crudini --merge /etc/ironic/ironic.conf < /tmp/ironic.conf && \
    rm /tmp/ironic.conf

# NOTE(elfosardo) removing building deps
# we should use lists for packages
RUN yum remove -y gcc python-devel

COPY ./runironic-api.sh /bin/runironic-api
COPY ./runironic-conductor.sh /bin/runironic-conductor
COPY ./rundnsmasq.sh /bin/rundnsmasq
COPY ./runhttpd.sh /bin/runhttpd
COPY ./runmariadb.sh /bin/runmariadb
COPY ./configure-ironic.sh /bin/configure-ironic.sh

# TODO(dtantsur): remove these 2 scripts if we decide to
# stop supporting running all 2 processes via one entry point.
COPY ./runhealthcheck.sh /bin/runhealthcheck
COPY ./runironic.sh /bin/runironic

COPY ./dnsmasq.conf /etc/dnsmasq.conf
COPY ./inspector.ipxe /tmp/inspector.ipxe
COPY ./dualboot.ipxe /tmp/dualboot.ipxe

ENTRYPOINT ["/bin/runironic"]
