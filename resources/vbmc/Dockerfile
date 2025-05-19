ARG BASE_IMAGE=docker.io/library/python:3.12-slim-bookworm

FROM $BASE_IMAGE

# image.version will be set by automation during build
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 VMBC container image"
LABEL org.opencontainers.image.documentation="https://docs.openstack.org/virtualbmc/latest/"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 VMBC"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/ironic-image"
LABEL org.opencontainers.image.vendor="Metal3-io"

ARG VIRTUALBMC_VERSION="3.2.0"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y libvirt-dev ssh gcc && \
    apt-get clean && \
    python3 -m pip install --no-cache-dir \
        virtualbmc=="${VIRTUALBMC_VERSION}" && \
    apt-get --purge autoremove -y gcc

CMD /usr/local/bin/vbmcd --foreground
