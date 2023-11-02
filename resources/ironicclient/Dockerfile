ARG BASE_IMAGE=quay.io/centos/centos:stream9
FROM $BASE_IMAGE

COPY ironic.profile /etc/profile.d/ironic.sh

RUN set -eux ; \
    export LANG=C.UTF-8; \
    BUILD_PACKAGES="gcc python3-pip" ; \
    REQUIRED_PACKAGES="" ; \
    yum update ; \
    yum install -y ${BUILD_PACKAGES} ${REQUIRED_PACKAGES} ; \
    pip install python-ironicclient ; \
    yum remove -y ${BUILD_PACKAGES}

CMD ["bash","-l"]
