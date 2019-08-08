FROM docker.io/centos:centos7
WORKDIR /root
RUN yum install -y python-requests

RUN curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python - -b stein current-tripleo

RUN yum update -y
#    #yum install -y openstack-ironic-api openstack-ironic-conductor \
#        python-PyMySQL python2-chardet

#RUN yum install -y epel-release && \
#    yum update

RUN yum install -y git

COPY clone_repos.sh /bin/clone_repos.sh

RUN chmod +x /bin/clone_repos.sh && /bin/clone_repos.sh

# COPY build_binaries.sh /bin/build_binaries.sh

# RUN chmod +x /bin/build_binaries.sh && /bin/build_binaries.sh

# RUN yum clean all


# FROM docker.io/centos:centos7

# Install some deps, including crudini
RUN yum install -y python-requests && \
    curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py | python - -b stein current-tripleo && \
    yum update -y && \
    yum install -y crudini iproute iptables dnsmasq httpd qemu-img-ev iscsi-initiator-utils \
    parted gdisk ipxe-bootimgs psmisc sysvinit-tools mariadb-server ipmitool

run yum clean all

# Copy the binaries!
#COPY --from=builder /root/build/ironic-api /usr/bin/ironic-api
#COPY --from=builder /root/build/ironic-conductor /usr/bin/ironic-conductor
#COPY --from=builder /root/build/ironic-dbsync /usr/bin/ironic-dbsync
# copy stock config
# already present
# RUN mkdir /etc/ironic


# need a starting point...
#COPY ironic/exam/ironic.conf /etc/ironic/ironic.conf

# Set the stage in the final container!
RUN mkdir /tftpboot && \
    cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /tftpboot/

COPY ./ironic.conf /tmp/ironic.conf
RUN crudini --merge /etc/ironic/ironic.conf < /tmp/ironic.conf && \
    rm /tmp/ironic.conf

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
