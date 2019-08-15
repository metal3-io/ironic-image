#!/bin/bash
#
# Copyright 2015 Hewlett-Packard Development Company, L.P.
# Copyright 2016 Intel Corporation
# Copyright 2016 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
## based on Ironic/devstack/upgrade/resources.sh

set -o errexit

source $GRENADE_DIR/grenaderc
source $GRENADE_DIR/functions

source $TOP_DIR/openrc admin admin

# Inspector relies on a couple of Ironic variables
source $TARGET_RELEASE_DIR/ironic/devstack/lib/ironic

INSPECTOR_DEVSTACK_DIR=$(cd $(dirname "$0")/.. && pwd)
source $INSPECTOR_DEVSTACK_DIR/plugin.sh

set -o xtrace


function early_create {
    :
}

function create {
    :
}

function verify {
    :
}

function verify_noapi {
    :
}

function destroy {
    :
}

# Dispatcher
case $1 in
    "early_create")
        early_create
        ;;
    "create")
        create
        ;;
    "verify_noapi")
        verify_noapi
        ;;
    "verify")
        verify
        ;;
    "destroy")
        destroy
        ;;
    "force_destroy")
        set +o errexit
        destroy
        ;;
esac
