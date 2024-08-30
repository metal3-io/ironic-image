#!/usr/bin/bash

# Ramdisk logs path
LOG_DIR="/shared/log/ironic/deploy"

inotifywait -m "${LOG_DIR}" -e close_write |
    while read -r path _action file; do
        echo "************ Contents of ${path}/${file} ramdisk log file bundle **************"
        tar -xOzvvf "${path}/${file}" | sed -e "s/^/${file}: /"
        rm -f "${path}/${file}"
    done
