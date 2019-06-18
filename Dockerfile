FROM docker.io/centos:centos7

RUN mkdir -p /root/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

COPY ./python-ironic-lib.spec /root/rpmbuild/SPECS/
COPY ./ironic.spec /root/rpmbuild/SPECS/
COPY ./rpm-sources/* /root/rpmbuild/SOURCES/

RUN yum install -y python-requests \
 && curl https://raw.githubusercontent.com/openstack/tripleo-repos/master/tripleo_repos/main.py| python - current-tripleo \
 && yum update -y \
 && yum install -y rpm-build yum-utils \
 && yum-builddep -y /root/rpmbuild/SPECS/python-ironic-lib.spec \
 && git clone https://github.com/openshift/ironic-lib.git \
 && cd ironic-lib \
 && python setup.py sdist \
 && VERSION=$(grep ^Version ironic_lib.egg-info/PKG-INFO | awk '{print $2}') \
 && cp ./dist/ironic-lib-${VERSION}.tar.gz /root/rpmbuild/SOURCES \
 && sed -i "/^Version/s/XXX/${VERSION}/" /root/rpmbuild/SPECS/python-ironic-lib.spec \
 && rpmbuild -v -bb --clean /root/rpmbuild/SPECS/python-ironic-lib.spec \
 && yum install -y /root/rpmbuild/RPMS/noarch/python2-ironic-lib-2.17.2.dev2-XXX.noarch.rpm \
 && cd - \
 && yum-builddep -y /root/rpmbuild/SPECS/ironic.spec \
 && git clone https://github.com/openshift/ironic.git \
 && cd ironic \
 && python setup.py sdist \
 && VERSION=$(grep ^Version ironic.egg-info/PKG-INFO | awk '{print $2}') \
 && cp ./dist/ironic-${VERSION}.tar.gz /root/rpmbuild/SOURCES \
 && sed -i "/^Version/s/XXX/${VERSION}/" /root/rpmbuild/SPECS/ironic.spec \
 && rpmbuild -v -bb --clean /root/rpmbuild/SPECS/ironic.spec \
 && yum install -y /root/rpmbuild/RPMS/noarch/openshift-ironic-common-${VERSION}-XXX.noarch.rpm \
 && yum install -y /root/rpmbuild/RPMS/noarch/openshift-ironic-api-${VERSION}-XXX.noarch.rpm \
 && yum install -y /root/rpmbuild/RPMS/noarch/openshift-ironic-conductor-${VERSION}-XXX.noarch.rpm \
 && yum install -y epel-release python-pip python-devel gcc crudini \
        iproute iptables dnsmasq httpd qemu-img-ev iscsi-initiator-utils parted gdisk ipxe-bootimgs psmisc sysvinit-tools \
        mariadb-server python-PyMySQL python2-chardet \
 && yum install -y python-configparser python-ironic-prometheus-exporter \
 && yum clean all

RUN mkdir /tftpboot \
 && cp /usr/share/ipxe/undionly.kpxe /usr/share/ipxe/ipxe.efi /tftpboot/

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
