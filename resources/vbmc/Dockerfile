ARG BASE_IMAGE=docker.io/library/python:3.9.18-slim-bookworm

FROM $BASE_IMAGE

ARG VIRTUALBMC_VERSION="3.2.0"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y libvirt-dev ssh gcc && \
    apt-get clean && \
    python3 -m pip install --no-cache-dir \
        virtualbmc=="${VIRTUALBMC_VERSION}" && \
    apt-get --purge autoremove -y gcc

CMD /usr/local/bin/vbmcd --foreground
