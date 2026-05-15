ARG BASE_IMAGE=docker.io/library/python:3.12-slim-bookworm

FROM $BASE_IMAGE

# image.version will be set by automation during build
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 Sushy Tools container image"
LABEL org.opencontainers.image.documentation="https://docs.openstack.org/sushy/latest/"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 Sushy Tools"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/ironic-image"
LABEL org.opencontainers.image.vendor="Metal3-io"

# Use a commit hash for merged changes or things like refs/changes/34/988434/1
# for in-progress gerrit reviews. Tags should work as well.
ARG SUSHY_TOOLS_VERSION="3b57e7a224804dd892b9d107d39e4b8b21ee975a"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y git libvirt-dev ssh gcc && \
    apt-get clean && \
    pip3 install --no-cache-dir \
        git+https://review.opendev.org/openstack/sushy-tools@${SUSHY_TOOLS_VERSION} \
        libvirt-python openstacksdk && \
    apt-get --purge autoremove -y gcc git

COPY redfish-emulator.sh /usr/local/bin/

CMD /usr/local/bin/redfish-emulator.sh
