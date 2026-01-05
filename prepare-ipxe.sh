#!/usr/bin/bash

set -euxo pipefail

echo "install_weak_deps=False" >> /etc/dnf/dnf.conf && \
echo "tsflags=nodocs" >> /etc/dnf/dnf.conf && \
echo "keepcache=1" >> /etc/dnf/dnf.conf && \
dnf install -y epel-release && \
dnf config-manager --set-disabled epel && \
dnf install -y git make xz-devel

# Install appropriate gcc binaries based on build architecture
if [[ "$TARGETARCH" == "amd64" ]]; then
    # On x86_64, we need native gcc for x86 builds and cross-compiler for arm64
    dnf install -y gcc && \
    dnf install --enablerepo=epel -y gcc-aarch64-linux-gnu gcc-c++-aarch64-linux-gnu
elif [[ "$TARGETARCH" == "arm64" ]]; then
    # On arm64, we need native gcc for arm64 builds and cross-compiler for x86_64
    dnf install -y gcc && \
    dnf install --enablerepo=epel -y gcc-x86_64-linux-gnu gcc-c++-x86_64-linux-gnu
else
    echo "ERROR: Unsupported build architecture: $TARGETARCH"
    exit 1
fi
