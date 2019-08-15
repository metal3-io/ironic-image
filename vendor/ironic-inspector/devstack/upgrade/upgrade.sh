#!/usr/bin/env bash
## based on Ironic/devstack/upgrade/upgrade.sh

# ``upgrade-inspector``

echo "*********************************************************************"
echo "Begin $0"
echo "*********************************************************************"

# Clean up any resources that may be in use
cleanup() {
    set +o errexit

    echo "*********************************************************************"
    echo "ERROR: Abort $0"
    echo "*********************************************************************"

    # Kill ourselves to signal any calling process
    trap 2; kill -2 $$
}

trap cleanup SIGHUP SIGINT SIGTERM

# Keep track of the grenade directory
RUN_DIR=$(cd $(dirname "$0") && pwd)

# Source params
source $GRENADE_DIR/grenaderc

# Import common functions
source $GRENADE_DIR/functions

# This script exits on an error so that errors don't compound and you see
# only the first error that occurred.
set -o errexit

# Upgrade Inspector
# =================

# Duplicate some setup bits from target DevStack
source $TARGET_DEVSTACK_DIR/stackrc
source $TARGET_DEVSTACK_DIR/lib/tls
source $TARGET_DEVSTACK_DIR/lib/nova
source $TARGET_DEVSTACK_DIR/lib/neutron-legacy
source $TARGET_DEVSTACK_DIR/lib/apache
source $TARGET_DEVSTACK_DIR/lib/keystone
source $TARGET_DEVSTACK_DIR/lib/database
source $TARGET_DEVSTACK_DIR/lib/rpc_backend

# Inspector relies on couple of Ironic variables
source $TARGET_RELEASE_DIR/ironic/devstack/lib/ironic

# Keep track of the DevStack directory
INSPECTOR_DEVSTACK_DIR=$(cd $(dirname "$0")/.. && pwd)
INSPECTOR_PLUGIN=$INSPECTOR_DEVSTACK_DIR/plugin.sh
source $INSPECTOR_PLUGIN

# Print the commands being run so that we can see the command that triggers
# an error.  It is also useful for following allowing as the install occurs.
set -o xtrace

initialize_database_backends

function wait_for_keystone {
    if ! wait_for_service $SERVICE_TIMEOUT ${KEYSTONE_AUTH_URI}/v$IDENTITY_API_VERSION/; then
        die $LINENO "keystone did not start"
    fi
}

# Save current config files for posterity
if  [[ -d $IRONIC_INSPECTOR_CONF_DIR ]] && [[ ! -d $SAVE_DIR/etc.inspector ]] ; then
    cp -pr $IRONIC_INSPECTOR_CONF_DIR $SAVE_DIR/etc.inspector
fi

# This call looks for install_<NAME>, which is install_inspector in our case:
# https://github.com/openstack-dev/devstack/blob/dec121114c3ea6f9e515a452700e5015d1e34704/lib/stack#L32
stack_install_service inspector

if is_inspector_dhcp_required; then
    stack_install_service inspector_dhcp
fi

$IRONIC_INSPECTOR_DBSYNC_BIN_FILE --config-file $IRONIC_INSPECTOR_CONF_FILE upgrade

# calls upgrade inspector for specific release
upgrade_project ironic-inspector $RUN_DIR $BASE_DEVSTACK_BRANCH $TARGET_DEVSTACK_BRANCH

# setup transport_url for rpc messaging
iniset_rpc_backend ironic-inspector $IRONIC_INSPECTOR_CONF_FILE

start_inspector
if is_inspector_dhcp_required; then
    start_inspector_dhcp
fi

# Don't succeed unless the services come up
ensure_services_started ironic-inspector

if is_inspector_dhcp_required; then
    ensure_services_started dnsmasq
fi

set +o xtrace
echo "*********************************************************************"
echo "SUCCESS: End $0"
echo "*********************************************************************"
