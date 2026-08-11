#!/usr/bin/bash

# Ramdisk logs path
export LOG_DIR="/shared/log/ironic/deploy"

mkdir -p "${LOG_DIR}"

# Function to process log files
process_log_file() {
    local FILEPATH="$1"
    # shellcheck disable=SC2155
    local FILENAME=$(basename "${FILEPATH}")

    echo "************ Contents of ${LOG_DIR}/${FILENAME} ramdisk log file bundle **************"
    tar -tzf "${FILEPATH}" | while read -r entry; do
        echo "${FILENAME}: **** Entry: ${entry} ****"
        tar -xOzf "${FILEPATH}" "${entry}" | sed -e "s/^/${FILENAME}: /"
        echo
    done
    rm -f "${FILEPATH}"
}

# Export the function so watchmedo can use it
export -f process_log_file

# Use watchmedo to monitor for file close events.
# NOTE: watchmedo (Python) never installs its own SIGTERM handler.
# Instead, keep this script (bash) as PID 1, run watchmedo as a child,
# and explicitly forward SIGTERM/SIGINT to it so the container stops
# promptly.
trap 'kill -TERM "${child_pid}" 2>/dev/null' TERM INT

# shellcheck disable=SC2016
watchmedo shell-command \
    --patterns="*" \
    --ignore-directories \
    --command='if [[ "${watch_event_type}" == "closed" ]]; then process_log_file "${watch_src_path}"; fi' \
    "${LOG_DIR}" &
child_pid=$!
wait "${child_pid}"
