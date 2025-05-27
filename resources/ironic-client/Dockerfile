ARG BASE_IMAGE=docker.io/library/python:3.12-slim-bookworm

FROM $BASE_IMAGE

# image.version will be set by automation during build
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 Ironic Client container image"
LABEL org.opencontainers.image.documentation="https://docs.openstack.org/python-ironicclient/latest/"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 Ironic Client"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/ironic-image"
LABEL org.opencontainers.image.vendor="Metal3-io"

# Help people find the actual baremetal command
COPY scripts/openstack /usr/bin/openstack

RUN apt-get update && \
    apt-get install -y genisoimage && \
    apt-get clean && \
    pip3 install --prefix /usr/local --no-cache-dir python-ironicclient && \
    chmod +x /usr/bin/openstack

ENTRYPOINT ["/usr/local/bin/baremetal"]
