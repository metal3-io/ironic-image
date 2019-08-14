#!/bin/bash

set -xe

source $(dirname $0)/common.sh

# Use a virtualenv to work around the fact that if the build host has
# a version of the package installed then pip refuses to install
# another version somewhere else, even if it isn't on the path.
rm -rf $INSTALL
virtualenv $INSTALL
source $INSTALL/bin/activate

for dir in $UNPACK/*
do
    echo
    echo $dir
    echo

    # Build a wheel to get around pbr's insistence on having a git
    # repository to calculate the version. We still get the wrong
    # version, but at least we get a version.
    (cd $dir && python setup.py bdist_wheel)

    pip install \
        --isolated \
        --no-deps \
        --disable-pip-version-check \
        --prefix $INSTALL \
        $dir/dist/*.whl
done
