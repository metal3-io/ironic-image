ARG BASE_IMAGE=docker.io/library/python:3.9.18-slim-bookworm

FROM $BASE_IMAGE

ARG SUSHY_TOOLS_VERSION="1.3.0"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y libvirt-dev ssh gcc && \
    apt-get clean && \
    pip3 install --no-cache-dir \
        sushy-tools==${SUSHY_TOOLS_VERSION} libvirt-python openstacksdk && \
    apt-get --purge autoremove -y gcc

COPY redfish-emulator.sh /usr/local/bin/

CMD /usr/local/bin/redfish-emulator.sh
