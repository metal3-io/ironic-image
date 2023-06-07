#!/usr/bin/bash
set -ex

PATCH_FILE="/tmp/${PATCH_LIST}"
VARS="PROJECT REFSPEC GIT_HOST"

dnf install -y python3-pip git-core

while IFS= read -r line; do
    # shellcheck disable=SC2086,SC2229
    IFS=' ' read -r $VARS <<< "$line"
    PROJ_NAME=$(echo "$PROJECT" | cut -d "/" -f2)
    PROJ_URL="${GIT_HOST:-"https://opendev.org"}/$PROJECT"

    cd /tmp
    git clone "$PROJ_URL"
    cd "$PROJ_NAME"
    git fetch "$PROJ_URL" "$REFSPEC"
    git checkout FETCH_HEAD

    SKIP_GENERATE_AUTHORS=1 SKIP_WRITE_GIT_CHANGELOG=1 python3 setup.py sdist
    pip3 install --prefix /usr dist/*.tar.gz
done < "$PATCH_FILE"

dnf remove -y python3-pip git-core
cd /
