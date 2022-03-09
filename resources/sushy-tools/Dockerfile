FROM registry.hub.docker.com/library/python:3.9

ARG SUSHY_TOOLS_VERSION="0.18.1"

RUN apt update && \
    apt install -y libvirt-dev && \
    apt clean && \
    pip3 install --no-cache-dir \
        sushy-tools==${SUSHY_TOOLS_VERSION} libvirt-python

CMD /usr/local/bin/sushy-emulator -i :: -p 8000 \
        --config /root/sushy/conf.py --debug
