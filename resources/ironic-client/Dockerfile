FROM quay.io/centos/centos:stream9

# Help people find the actual baremetal command
COPY scripts/openstack /usr/bin/openstack

RUN dnf install -y python3 python3-pip genisoimage && \
    pip install python-ironicclient --prefix /usr --no-cache-dir && \
    chmod +x /usr/bin/openstack && \
    dnf update -y && \
    dnf clean all && \
    rm -rf /var/cache/{yum,dnf}/*

ENTRYPOINT ["/usr/bin/baremetal"]
