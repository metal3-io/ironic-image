#!/usr/bin/bash

# Ramdisk logs path
LOG_DIR="/shared/log/ironic/deploy"

python3 -m pyinotify -e IN_CLOSE_WRITE -v "${LOG_DIR}" |
    while read -r path _action file; do
        echo "************ Contents of ${path}/${file} ramdisk log file bundle **************"
        tar -xOzvvf "${path}/${file}" | sed -e "s/^/${file}: /"
        rm -f "${path}/${file}"
    done
