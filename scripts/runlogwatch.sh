#!/usr/bin/bash

# Ramdisk logs path
LOG_DIR="/shared/log/ironic/deploy"

while :; do
    if ! ls "${LOG_DIR}"/*.tar.gz 1> /dev/null 2>&1; then
        continue
    fi

    for fn in "${LOG_DIR}"/*.tar.gz; do
        echo "************ Contents of $fn ramdisk log file bundle **************"
        tar -xOzvvf "$fn" | sed -e "s/^/$(basename "$fn"): /"
        rm -f "$fn"
    done

    sleep 5
done
