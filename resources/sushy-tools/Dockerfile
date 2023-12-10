FROM docker.io/library/python:3.9

ARG SUSHY_TOOLS_VERSION="1.0.1"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y libvirt-dev && \
    apt-get clean && \
    pip3 install --no-cache-dir \
        sushy-tools==${SUSHY_TOOLS_VERSION} libvirt-python openstacksdk

COPY redfish-emulator.sh /usr/local/bin/

CMD /usr/local/bin/redfish-emulator.sh
