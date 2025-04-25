#!/usr/bin/bash

# Ramdisk logs path
LOG_DIR="/shared/log/ironic/deploy"

mkdir -p "${LOG_DIR}"

# shellcheck disable=SC2034
python3 -m pyinotify --raw-format -e IN_CLOSE_WRITE -v "${LOG_DIR}" |
    while read -r event dir mask maskname filename filepath pathname wd; do
        #NOTE(elfosardo): a pyinotify event looks like this:
        # <Event dir=False mask=0x8 maskname=IN_CLOSE_WRITE name=mylogs.gzip path=/shared/log/ironic/deploy pathname=/shared/log/ironic/deploy/mylogs.gzip wd=1 >
        FILENAME=$(echo "${filename}" | cut -d'=' -f2-)
        echo "************ Contents of ${LOG_DIR}/${FILENAME} ramdisk log file bundle **************"
        tar -tzf "${LOG_DIR}/${FILENAME}" | while read -r entry; do
            echo "${FILENAME}: **** Entry: ${entry} ****"
            tar -xOzf "${LOG_DIR}/${FILENAME}" "${entry}" | sed -e "s/^/${FILENAME}: /"
            echo
        done
        rm -f "${LOG_DIR}/${FILENAME}"
    done
