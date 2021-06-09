#!/usr/bin/bash

# Ramdisk logs path
LOG_DIRS=("/shared/log/ironic/deploy" "/shared/log/ironic-inspector/ramdisk")

for LOG_DIR in ${LOG_DIRS[@]}; do
    if [[ -d $LOG_DIR ]]; then
        while :
        do
            until  ls "${LOG_DIR}"/*.tar.gz 1> /dev/null 2>&1
            do
                sleep 5
            done

            for fn in "${LOG_DIR}"/*.tar.gz
            do
                echo "************ Contents of $fn ramdisk log file bundle **************"
                tar -xOzvvf $fn | sed -e "s/^/$(basename $fn): /"
                rm -f $fn
            done
        done
    fi
done
