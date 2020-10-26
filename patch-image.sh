#!/usr/bin/bash
set -ex

patch_file="/tmp/${PATCH_LIST}"

while IFS= read -r line
do
    # each line is in the form "project_dir refsspec" where:
    # - project is the last part of the project url including the org,
    # for example openstack/ironic
    # - refspec is the gerrit refspec of the patch we want to test,
    # for example refs/changes/67/759567/1
    PROJECT=$(echo $line | cut -d " " -f1)
    PROJ_NAME=$(echo $PROJECT | cut -d "/" -f2)
    PROJ_URL="https://opendev.org/$PROJECT"
    REFSPEC=$(echo $line | cut -d " " -f2)

    cd /tmp
    git clone "$PROJ_URL"
    cd "$PROJ_NAME"
    git fetch "$PROJ_URL" "$REFSPEC"
    git checkout FETCH_HEAD

    SKIP_GENERATE_AUTHORS=1 SKIP_WRITE_GIT_CHANGELOG=1 python3 setup.py sdist
    pip3 install dist/*.tar.gz
done < "$patch_file"

cd /

