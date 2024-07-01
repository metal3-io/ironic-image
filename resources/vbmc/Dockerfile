ARG BASE_IMAGE=quay.io/centos/centos:stream9

FROM $BASE_IMAGE

# Configure OpenStack repos from RDO https://www.rdoproject.org
RUN dnf upgrade -y && \
  dnf install -y dnf-plugins-core && \
  dnf config-manager --enable crb && \
  curl https://trunk.rdoproject.org/centos9-master/puppet-passed-ci/delorean.repo -o /etc/yum.repos.d/rdo.repo && \
  curl https://trunk.rdoproject.org/centos9-master/delorean-deps.repo -o /etc/yum.repos.d/rdo-deps.repo && \
  dnf install -y python3-virtualbmc && \
  dnf clean all && \
  rm -rf /var/cache/{yum,dnf}/*

CMD /usr/bin/vbmcd --foreground
