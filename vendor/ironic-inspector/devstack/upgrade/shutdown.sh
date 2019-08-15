#!/bin/bash
#
# based on Ironic/devstack/upgrade/shutdown.sh

set -o errexit

source $GRENADE_DIR/grenaderc
source $GRENADE_DIR/functions

# We need base DevStack functions for this
source $BASE_DEVSTACK_DIR/functions
source $BASE_DEVSTACK_DIR/stackrc # needed for status directory
source $BASE_DEVSTACK_DIR/lib/tls
source $BASE_DEVSTACK_DIR/lib/apache

# Inspector relies on a couple of Ironic variables
source $TARGET_RELEASE_DIR/ironic/devstack/lib/ironic

# Keep track of the DevStack directory
INSPECTOR_DEVSTACK_DIR=$(cd $(dirname "$0")/.. && pwd)
source $INSPECTOR_DEVSTACK_DIR/plugin.sh


set -o xtrace

stop_inspector
if is_inspector_dhcp_required; then
    stop_inspector_dhcp
fi
