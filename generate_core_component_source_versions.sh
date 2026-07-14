#!/bin/bash
set -eu
set -o pipefail

DEBUG=false
[[ "${1:-}" == "--debug" ]] && DEBUG=true
debug() {
    if [[ "${DEBUG}" == true ]]; then
        echo "[DEBUG] $*" >&2
    fi
}

CURRENT_DIR="$(dirname "${BASH_SOURCE[0]}")"
VERSION_DIR="${CURRENT_DIR}/versioncheck"
mkdir -p "${VERSION_DIR}"

for component in 'NGS:networking-generic-switch' 'IRONIC:ironic'; do
    REPO_NAME="${component#*:}"
    COMPONENT_MARKER="${component%:*}"
    debug "REPO NAME:${REPO_NAME} ----- COMPONENT MARKER:${COMPONENT_MARKER}"

    EXPRESSION="^ARG ${COMPONENT_MARKER}_SOURCE=\K[[:xdigit:]]* # .*"
    COMMIT_LINE="$(grep -oP "${EXPRESSION}" "${CURRENT_DIR}/Dockerfile" )"
    debug "Found ${COMPONENT_MARKER} source in Dockerfile:${COMMIT_LINE}"

    COMMIT_SHA="${COMMIT_LINE%[[:space:]]#[[:space:]]*}"
    BRANCH="${COMMIT_LINE#*[[:space:]]#[[:space:]]}"
    rm -rf "${VERSION_DIR:?}/${REPO_NAME}" || true
    git clone -q -b "${BRANCH}" --filter=blob:none \
        "https://opendev.org/openstack/${REPO_NAME}.git" \
        "${VERSION_DIR:?}/${REPO_NAME}" &>/dev/null
    GIT_DESCRIBE="$(git -C "${VERSION_DIR}/${REPO_NAME}" describe --tags "${COMMIT_SHA}")"

    echo "${REPO_NAME}-version=${GIT_DESCRIBE}"
done

