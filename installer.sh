#!/bin/bash

SOURCE_DIR="/var/tmp/sources-install/"
REQUIREMENTS_FILE="/var/tmp/actual-reqs.txt"

mkdir -p $SOURCE_DIR

pip install --upgrade pip

pip download -r $REQUIREMENTS_FILE -d $SOURCE_DIR

pip install --no-deps --no-index --find-links $SOURCE_DIR -r $REQUIREMENTS_FILE

rm -fr $SOURCE_DIR
