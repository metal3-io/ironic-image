FROM registry.hub.docker.com/library/python:3.9

ARG SUSHY_TOOLS_VERSION="0.21.0"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y libvirt-dev && \
    apt-get clean && \
    pip3 install --no-cache-dir \
        sushy-tools==${SUSHY_TOOLS_VERSION} libvirt-python

CMD /usr/local/bin/sushy-emulator -i :: -p 8000 \
        --config /root/sushy/conf.py --debug
