#!/bin/bash

DOWNLOAD=download
UNPACK=vendor
INSTALL=install

function update_dep_from_pypi {
    local dep=$1
    local version=$2

    mkdir -p $DOWNLOAD

    # pip will recognize if it has already downloaded the file, so
    # just go ahead and do it.
    pip download \
        -d $DOWNLOAD \
        --no-deps \
        --no-binary :all: \
        ${dep}===${version}

    unpack_sdist ${dep} ${version}
}

function unpack_sdist {
    local dep=$1
    local version=$2

    mkdir -p $UNPACK

    # Clean up the old version. We will be writing to the same
    # directory, eventually, so git will tell us what actually chaged.
    rm -rf $UNPACK/${dep}

    for sdist in $DOWNLOAD/${dep}-${version}.tar.*
    do
        if [[ $sdist =~ \.gz ]]; then
            zopt=z
        elif [[ $sdist =~ \.bz2 ]]; then
            zopt=j
        else
            echo "Unknown file format $sdist"
            return 1
        fi

        tar --directory $UNPACK \
            -x -v -${zopt} \
            -f $sdist \
            --unlink-first --recursive-unlink

        # The sdist will create a directory with the project version
        # number in the name. We want to remove that so that the same
        # dependency is always in the same directory, to make it
        # easier to track updates to that dependency.
        mv $UNPACK/${dep}-${version} $UNPACK/$dep
    done
}

function update_dep_from_git {
    local dep=$1
    local repo=$2
    local ref=$3

    mkdir -p $UNPACK

    # Remove any previously cloned version of the dependency.
    rm -rf $DOWNLOAD/${dep}

    git clone ${repo} $DOWNLOAD/$dep

    # Build an sdist so we are sure to have a version number (pbr
    # requires metadata or git history).
    (cd $DOWNLOAD/${dep} && git checkout ${ref} && python setup.py sdist)

    # Move the sdist into the download directory so unpack_sdist can
    # find it.
    mv $DOWNLOAD/$dep/dist/* $DOWNLOAD/

    # Determine the version that we have.
    version=$(cd $DOWNLOAD/${dep} && python setup.py --version)

    unpack_sdist $dep $version
}
