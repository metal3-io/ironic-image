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

ARG SUSHY_TOOLS_VERSION="2.2.0"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y libvirt-dev ssh gcc && \
    apt-get clean && \
    pip3 install --no-cache-dir \
        sushy-tools==${SUSHY_TOOLS_VERSION} libvirt-python openstacksdk && \
    apt-get --purge autoremove -y gcc

COPY redfish-emulator.sh /usr/local/bin/

CMD /usr/local/bin/redfish-emulator.sh
