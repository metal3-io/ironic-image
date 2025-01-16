ARG BASE_IMAGE=docker.io/library/python:3.9-slim-bookworm

FROM $BASE_IMAGE

# Help people find the actual baremetal command
COPY scripts/openstack /usr/bin/openstack

RUN apt-get update && \
    apt-get install -y genisoimage && \
    apt-get clean && \
    pip3 install --prefix /usr/local --no-cache-dir python-ironicclient && \
    chmod +x /usr/bin/openstack

ENTRYPOINT ["/usr/local/bin/baremetal"]
