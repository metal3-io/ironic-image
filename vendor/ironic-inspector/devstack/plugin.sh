#!/usr/bin/env bash

# This package should be tested under python 3, when the job enables Python 3
enable_python3_package ironic-inspector

IRONIC_INSPECTOR_DEBUG=${IRONIC_INSPECTOR_DEBUG:-True}
IRONIC_INSPECTOR_DIR=$DEST/ironic-inspector
IRONIC_INSPECTOR_DATA_DIR=$DATA_DIR/ironic-inspector
IRONIC_INSPECTOR_BIN_DIR=$(get_python_exec_prefix)
IRONIC_INSPECTOR_BIN_FILE=$IRONIC_INSPECTOR_BIN_DIR/ironic-inspector
IRONIC_INSPECTOR_DBSYNC_BIN_FILE=$IRONIC_INSPECTOR_BIN_DIR/ironic-inspector-dbsync
IRONIC_INSPECTOR_CONF_DIR=${IRONIC_INSPECTOR_CONF_DIR:-/etc/ironic-inspector}
IRONIC_INSPECTOR_CONF_FILE=$IRONIC_INSPECTOR_CONF_DIR/inspector.conf
IRONIC_INSPECTOR_CMD="$IRONIC_INSPECTOR_BIN_FILE --config-file $IRONIC_INSPECTOR_CONF_FILE"
IRONIC_INSPECTOR_DHCP_CONF_FILE=$IRONIC_INSPECTOR_CONF_DIR/dnsmasq.conf
IRONIC_INSPECTOR_ROOTWRAP_CONF_FILE=$IRONIC_INSPECTOR_CONF_DIR/rootwrap.conf
IRONIC_INSPECTOR_ADMIN_USER=${IRONIC_INSPECTOR_ADMIN_USER:-ironic-inspector}
IRONIC_INSPECTOR_AUTH_CACHE_DIR=${IRONIC_INSPECTOR_AUTH_CACHE_DIR:-/var/cache/ironic-inspector}
IRONIC_INSPECTOR_DHCP_FILTER=${IRONIC_INSPECTOR_DHCP_FILTER:-iptables}
if [[ -n ${IRONIC_INSPECTOR_MANAGE_FIREWALL} ]] ; then
    echo "IRONIC_INSPECTOR_MANAGE_FIREWALL is deprecated." >&2
    echo "Please, use IRONIC_INSPECTOR_DHCP_FILTER == noop/iptables/dnsmasq instead." >&2
    if [[ "$IRONIC_INSPECTOR_DHCP_FILTER" != "iptables" ]] ; then
        # both manage firewall and filter driver set together but driver isn't iptables
        echo "Inconsistent configuration: IRONIC_INSPECTOR_MANAGE_FIREWALL used while" >&2
        echo "IRONIC_INSPECTOR_DHCP_FILTER == $IRONIC_INSPECTOR_DHCP_FILTER" >&2
        exit 1
    fi
    if [[ $(trueorfalse True IRONIC_INSPECTOR_MANAGE_FIREWALL) == "False" ]] ; then
        echo "IRONIC_INSPECTOR_MANAGE_FIREWALL == False" >&2
        echo "Setting IRONIC_INSPECTOR_DHCP_FILTER=noop" >&2
        IRONIC_INSPECTOR_DHCP_FILTER=noop
    fi
fi

# dnsmasq dhcp filter configuration
# override the default hostsdir so devstack collects the MAC files (/etc)
IRONIC_INSPECTOR_DHCP_HOSTSDIR=${IRONIC_INSPECTOR_DHCP_HOSTSDIR:-/etc/ironic-inspector/dhcp-hostsdir}
IRONIC_INSPECTOR_DNSMASQ_STOP_COMMAND=${IRONIC_INSPECTOR_DNSMASQ_STOP_COMMAND:-systemctl stop devstack@ironic-inspector-dhcp}
IRONIC_INSPECTOR_DNSMASQ_START_COMMAND=${IRONIC_INSPECTOR_DNSMASQ_START_COMMAND:-systemctl start devstack@ironic-inspector-dhcp}

IRONIC_INSPECTOR_HOST=$HOST_IP
IRONIC_INSPECTOR_PORT=5050
IRONIC_INSPECTOR_URI="http://$IRONIC_INSPECTOR_HOST:$IRONIC_INSPECTOR_PORT"
IRONIC_INSPECTOR_BUILD_RAMDISK=$(trueorfalse False IRONIC_INSPECTOR_BUILD_RAMDISK)
IRONIC_AGENT_KERNEL_URL=${IRONIC_AGENT_KERNEL_URL:-http://tarballs.openstack.org/ironic-python-agent/coreos/files/coreos_production_pxe.vmlinuz}
IRONIC_AGENT_RAMDISK_URL=${IRONIC_AGENT_RAMDISK_URL:-http://tarballs.openstack.org/ironic-python-agent/coreos/files/coreos_production_pxe_image-oem.cpio.gz}
IRONIC_INSPECTOR_COLLECTORS=${IRONIC_INSPECTOR_COLLECTORS:-default,logs,pci-devices}
IRONIC_INSPECTOR_RAMDISK_LOGDIR=${IRONIC_INSPECTOR_RAMDISK_LOGDIR:-$IRONIC_INSPECTOR_DATA_DIR/ramdisk-logs}
IRONIC_INSPECTOR_ALWAYS_STORE_RAMDISK_LOGS=${IRONIC_INSPECTOR_ALWAYS_STORE_RAMDISK_LOGS:-True}
IRONIC_INSPECTOR_TIMEOUT=${IRONIC_INSPECTOR_TIMEOUT:-600}
IRONIC_INSPECTOR_CLEAN_UP_PERIOD=${IRONIC_INSPECTOR_CLEAN_UP_PERIOD:-}
# These should not overlap with other ranges/networks
IRONIC_INSPECTOR_INTERNAL_IP=${IRONIC_INSPECTOR_INTERNAL_IP:-172.24.42.254}
IRONIC_INSPECTOR_INTERNAL_SUBNET_SIZE=${IRONIC_INSPECTOR_INTERNAL_SUBNET_SIZE:-24}
IRONIC_INSPECTOR_DHCP_RANGE=${IRONIC_INSPECTOR_DHCP_RANGE:-172.24.42.100,172.24.42.253}
IRONIC_INSPECTOR_INTERFACE=${IRONIC_INSPECTOR_INTERFACE:-br-inspector}
IRONIC_INSPECTOR_INTERFACE_PHYSICAL=$(trueorfalse False IRONIC_INSPECTOR_INTERFACE_PHYSICAL)
IRONIC_INSPECTOR_INTERNAL_URI="http://$IRONIC_INSPECTOR_INTERNAL_IP:$IRONIC_INSPECTOR_PORT"
IRONIC_INSPECTOR_INTERNAL_IP_WITH_NET="$IRONIC_INSPECTOR_INTERNAL_IP/$IRONIC_INSPECTOR_INTERNAL_SUBNET_SIZE"
# Whether DevStack will be setup for bare metal or VMs
IRONIC_IS_HARDWARE=$(trueorfalse False IRONIC_IS_HARDWARE)
IRONIC_INSPECTOR_NODE_NOT_FOUND_HOOK=${IRONIC_INSPECTOR_NODE_NOT_FOUND_HOOK:-""}
IRONIC_INSPECTOR_OVS_PORT=${IRONIC_INSPECTOR_OVS_PORT:-brbm-inspector}
IRONIC_INSPECTOR_EXTRA_KERNEL_CMDLINE=${IRONIC_INSPECTOR_EXTRA_KERNEL_CMDLINE:-""}
IRONIC_INSPECTOR_POWER_OFF=${IRONIC_INSPECTOR_POWER_OFF:-True}
if is_service_enabled swift; then
    DEFAULT_DATA_STORE=swift
else
    DEFAULT_DATA_STORE=database
fi
IRONIC_INSPECTOR_INTROSPECTION_DATA_STORE=${IRONIC_INSPECTOR_INTROSPECTION_DATA_STORE:-$DEFAULT_DATA_STORE}
GITDIR["python-ironic-inspector-client"]=$DEST/python-ironic-inspector-client
GITREPO["python-ironic-inspector-client"]=${IRONIC_INSPECTOR_CLIENT_REPO:-${GIT_BASE}/openstack/python-ironic-inspector-client.git}
GITBRANCH["python-ironic-inspector-client"]=${IRONIC_INSPECTOR_CLIENT_BRANCH:-master}

# This is defined in ironic's devstack plugin. Redefine it just in case, and
# insert "inspector" if it's missing.
IRONIC_ENABLED_INSPECT_INTERFACES=${IRONIC_ENABLED_INSPECT_INTERFACES:-"inspector,no-inspect,fake"}
if [[ "$IRONIC_ENABLED_INSPECT_INTERFACES" != *inspector* ]]; then
    IRONIC_ENABLED_INSPECT_INTERFACES="inspector,$IRONIC_ENABLED_INSPECT_INTERFACES"
fi

### Utilities

function mkdir_chown_stack {
    if [[ ! -d "$1" ]]; then
        sudo mkdir -p "$1"
    fi
    sudo chown $STACK_USER "$1"
}

function inspector_iniset {
    local section=$1
    local option=$2
    shift 2
    # value in iniset is at $4; wrapping in quotes
    iniset "$IRONIC_INSPECTOR_CONF_FILE" $section $option "$*"
}

### Install-start-stop

function install_inspector {
    setup_develop $IRONIC_INSPECTOR_DIR
}

function install_inspector_dhcp {
    install_package dnsmasq
}

function install_inspector_client {
    if use_library_from_git python-ironic-inspector-client; then
        git_clone_by_name python-ironic-inspector-client
        setup_dev_lib python-ironic-inspector-client
    else
        pip_install_gr python-ironic-inspector-client
    fi
}

function start_inspector {
    run_process ironic-inspector "$IRONIC_INSPECTOR_CMD"
}

function is_inspector_dhcp_required {
    [[ "$IRONIC_INSPECTOR_MANAGE_FIREWALL" == "True" ]] || \
    [[ "${IRONIC_INSPECTOR_DHCP_FILTER:-iptables}" != "noop" ]]
}

function start_inspector_dhcp {
    # NOTE(dtantsur): USE_SYSTEMD requires an absolute path
    run_process ironic-inspector-dhcp \
        "$(which dnsmasq) --conf-file=$IRONIC_INSPECTOR_DHCP_CONF_FILE" \
        "" root
}

function stop_inspector {
    stop_process ironic-inspector
}

function stop_inspector_dhcp {
    stop_process ironic-inspector-dhcp
}

### Configuration

function prepare_tftp {
    IRONIC_INSPECTOR_IMAGE_PATH="$TOP_DIR/files/ironic-inspector"
    IRONIC_INSPECTOR_KERNEL_PATH="$IRONIC_INSPECTOR_IMAGE_PATH.kernel"
    IRONIC_INSPECTOR_INITRAMFS_PATH="$IRONIC_INSPECTOR_IMAGE_PATH.initramfs"
    IRONIC_INSPECTOR_CALLBACK_URI="$IRONIC_INSPECTOR_INTERNAL_URI/v1/continue"

    IRONIC_INSPECTOR_KERNEL_CMDLINE="$IRONIC_INSPECTOR_EXTRA_KERNEL_CMDLINE ipa-inspection-callback-url=$IRONIC_INSPECTOR_CALLBACK_URI"
    IRONIC_INSPECTOR_KERNEL_CMDLINE="$IRONIC_INSPECTOR_KERNEL_CMDLINE ipa-api-url=$SERVICE_PROTOCOL://$SERVICE_HOST/baremetal"
    IRONIC_INSPECTOR_KERNEL_CMDLINE="$IRONIC_INSPECTOR_KERNEL_CMDLINE ipa-insecure=1 systemd.journald.forward_to_console=yes"
    IRONIC_INSPECTOR_KERNEL_CMDLINE="$IRONIC_INSPECTOR_KERNEL_CMDLINE vga=normal console=tty0 console=ttyS0"
    IRONIC_INSPECTOR_KERNEL_CMDLINE="$IRONIC_INSPECTOR_KERNEL_CMDLINE ipa-inspection-collectors=$IRONIC_INSPECTOR_COLLECTORS"
    IRONIC_INSPECTOR_KERNEL_CMDLINE="$IRONIC_INSPECTOR_KERNEL_CMDLINE ipa-debug=1"
    if [[ "$IRONIC_INSPECTOR_BUILD_RAMDISK" == "True" ]]; then
        if [ ! -e "$IRONIC_INSPECTOR_KERNEL_PATH" -o ! -e "$IRONIC_INSPECTOR_INITRAMFS_PATH" ]; then
            build_ipa_ramdisk "$IRONIC_INSPECTOR_KERNEL_PATH" "$IRONIC_INSPECTOR_INITRAMFS_PATH"
        fi
    else
        # download the agent image tarball
        if [ ! -e "$IRONIC_INSPECTOR_KERNEL_PATH" -o ! -e "$IRONIC_INSPECTOR_INITRAMFS_PATH" ]; then
            if [ -e "$IRONIC_DEPLOY_KERNEL" -a -e "$IRONIC_DEPLOY_RAMDISK" ]; then
                cp $IRONIC_DEPLOY_KERNEL $IRONIC_INSPECTOR_KERNEL_PATH
                cp $IRONIC_DEPLOY_RAMDISK $IRONIC_INSPECTOR_INITRAMFS_PATH
            else
                wget "$IRONIC_AGENT_KERNEL_URL" -O $IRONIC_INSPECTOR_KERNEL_PATH
                wget "$IRONIC_AGENT_RAMDISK_URL" -O $IRONIC_INSPECTOR_INITRAMFS_PATH
            fi
        fi
    fi

    if [[ "$IRONIC_IPXE_ENABLED" == "True" ]] ; then
        cp $IRONIC_INSPECTOR_KERNEL_PATH $IRONIC_HTTP_DIR/ironic-inspector.kernel
        cp $IRONIC_INSPECTOR_INITRAMFS_PATH $IRONIC_HTTP_DIR

        cat > "$IRONIC_HTTP_DIR/ironic-inspector.ipxe" <<EOF
#!ipxe

dhcp

kernel http://$IRONIC_HTTP_SERVER:$IRONIC_HTTP_PORT/ironic-inspector.kernel BOOTIF=\${mac} $IRONIC_INSPECTOR_KERNEL_CMDLINE
initrd http://$IRONIC_HTTP_SERVER:$IRONIC_HTTP_PORT/ironic-inspector.initramfs
boot
EOF
    else
        mkdir_chown_stack "$IRONIC_TFTPBOOT_DIR/pxelinux.cfg"
        cp $IRONIC_INSPECTOR_KERNEL_PATH $IRONIC_TFTPBOOT_DIR/ironic-inspector.kernel
        cp $IRONIC_INSPECTOR_INITRAMFS_PATH $IRONIC_TFTPBOOT_DIR

        cat > "$IRONIC_TFTPBOOT_DIR/pxelinux.cfg/default" <<EOF
default inspect

label inspect
kernel ironic-inspector.kernel
append initrd=ironic-inspector.initramfs $IRONIC_INSPECTOR_KERNEL_CMDLINE

ipappend 3
EOF
    fi
}

function inspector_configure_auth_for {
    inspector_iniset $1 auth_type password
    inspector_iniset $1 auth_url "$KEYSTONE_SERVICE_URI"
    inspector_iniset $1 username $IRONIC_INSPECTOR_ADMIN_USER
    inspector_iniset $1 password $SERVICE_PASSWORD
    inspector_iniset $1 project_name $SERVICE_PROJECT_NAME
    inspector_iniset $1 user_domain_id default
    inspector_iniset $1 project_domain_id default
    inspector_iniset $1 cafile $SSL_BUNDLE_FILE
    inspector_iniset $1 region_name $REGION_NAME
}

function is_dnsmasq_filter_required {
    [[ "$IRONIC_INSPECTOR_DHCP_FILTER" == "dnsmasq" ]]
}

function configure_inspector_pxe_filter_dnsmasq {
    mkdir_chown_stack $IRONIC_INSPECTOR_DHCP_HOSTSDIR
    inspector_iniset pxe_filter driver dnsmasq
    inspector_iniset dnsmasq_pxe_filter dhcp_hostsdir $IRONIC_INSPECTOR_DHCP_HOSTSDIR
    inspector_iniset dnsmasq_pxe_filter dnsmasq_stop_command "$IRONIC_INSPECTOR_DNSMASQ_STOP_COMMAND"
    inspector_iniset dnsmasq_pxe_filter dnsmasq_start_command "$IRONIC_INSPECTOR_DNSMASQ_START_COMMAND"
}

function configure_dnsmasq_dhcp_hostsdir {
    sed -ie '/dhcp-hostsdir.*=/d' $IRONIC_INSPECTOR_DHCP_CONF_FILE
    echo "dhcp-hostsdir=$IRONIC_INSPECTOR_DHCP_HOSTSDIR" >> $IRONIC_INSPECTOR_DHCP_CONF_FILE
}

function _dnsmasq_rootwrap_ctl_tail {
    # cut off the command head and amend white-spaces with commas
    shift
    local bits=$*
    echo ${bits//\ /, }
}

function configure_inspector_dnsmasq_rootwrap {
    # turn the ctl commands into filter rules and dump the roorwrap file
    local stop_cmd=( $IRONIC_INSPECTOR_DNSMASQ_STOP_COMMAND )
    local start_cmd=( $IRONIC_INSPECTOR_DNSMASQ_START_COMMAND )

    local stop_cmd_tail=$( _dnsmasq_rootwrap_ctl_tail ${stop_cmd[@]} )
    local start_cmd_tail=$( _dnsmasq_rootwrap_ctl_tail ${start_cmd[@]} )

    cat > "$IRONIC_INSPECTOR_CONF_DIR/rootwrap.d/ironic-inspector-dnsmasq.filters" <<EOF
[Filters]
# ironic_inspector/pxe_filter/dnsmasq.py
${stop_cmd[0]}: CommandFilter, ${stop_cmd[0]}, root, ${stop_cmd_tail}
${start_cmd[0]}: CommandFilter, ${start_cmd[0]}, root, ${start_cmd_tail}
EOF

}

function configure_inspector {
    mkdir_chown_stack "$IRONIC_INSPECTOR_CONF_DIR"
    mkdir_chown_stack "$IRONIC_INSPECTOR_DATA_DIR"

    create_service_user "$IRONIC_INSPECTOR_ADMIN_USER" "admin"

    # start with a fresh config file
    rm -f "$IRONIC_INSPECTOR_CONF_FILE"

    inspector_iniset DEFAULT debug $IRONIC_INSPECTOR_DEBUG
    inspector_configure_auth_for ironic
    inspector_configure_auth_for service_catalog
    configure_auth_token_middleware $IRONIC_INSPECTOR_CONF_FILE $IRONIC_INSPECTOR_ADMIN_USER $IRONIC_INSPECTOR_AUTH_CACHE_DIR/api

    inspector_iniset DEFAULT listen_port $IRONIC_INSPECTOR_PORT
    inspector_iniset DEFAULT listen_address 0.0.0.0  # do not change

    inspector_iniset pxe_filter driver $IRONIC_INSPECTOR_DHCP_FILTER
    inspector_iniset iptables dnsmasq_interface $IRONIC_INSPECTOR_INTERFACE
    inspector_iniset database connection `database_connection_url ironic_inspector`

    inspector_iniset processing power_off $IRONIC_INSPECTOR_POWER_OFF

    iniset_rpc_backend ironic-inspector $IRONIC_INSPECTOR_CONF_FILE

    if is_service_enabled swift; then
        configure_inspector_swift
    fi

    inspector_iniset processing store_data $IRONIC_INSPECTOR_INTROSPECTION_DATA_STORE

    iniset "$IRONIC_CONF_FILE" inspector enabled True
    iniset "$IRONIC_CONF_FILE" inspector service_url $IRONIC_INSPECTOR_URI

    setup_logging $IRONIC_INSPECTOR_CONF_FILE DEFAULT

    cp "$IRONIC_INSPECTOR_DIR/rootwrap.conf" "$IRONIC_INSPECTOR_ROOTWRAP_CONF_FILE"
    cp -r "$IRONIC_INSPECTOR_DIR/rootwrap.d" "$IRONIC_INSPECTOR_CONF_DIR"
    local ironic_inspector_rootwrap=$(get_rootwrap_location ironic-inspector)
    local rootwrap_sudoer_cmd="$ironic_inspector_rootwrap $IRONIC_INSPECTOR_CONF_DIR/rootwrap.conf *"

    # Set up the rootwrap sudoers for ironic-inspector
    local tempfile=`mktemp`
    echo "$STACK_USER ALL=(root) NOPASSWD: $rootwrap_sudoer_cmd" >$tempfile
    chmod 0640 $tempfile
    sudo chown root:root $tempfile
    sudo mv $tempfile /etc/sudoers.d/ironic-inspector-rootwrap

    inspector_iniset DEFAULT rootwrap_config $IRONIC_INSPECTOR_ROOTWRAP_CONF_FILE

    mkdir_chown_stack "$IRONIC_INSPECTOR_RAMDISK_LOGDIR"
    inspector_iniset processing ramdisk_logs_dir "$IRONIC_INSPECTOR_RAMDISK_LOGDIR"
    inspector_iniset processing always_store_ramdisk_logs "$IRONIC_INSPECTOR_ALWAYS_STORE_RAMDISK_LOGS"
    if [ -n "$IRONIC_INSPECTOR_NODE_NOT_FOUND_HOOK" ]; then
        inspector_iniset processing node_not_found_hook "$IRONIC_INSPECTOR_NODE_NOT_FOUND_HOOK"
    fi
    inspector_iniset DEFAULT timeout $IRONIC_INSPECTOR_TIMEOUT
    if [ -n "$IRONIC_INSPECTOR_CLEAN_UP_PERIOD" ]; then
        inspector_iniset DEFAULT clean_up_period "$IRONIC_INSPECTOR_CLEAN_UP_PERIOD"
    fi
    get_or_create_service "ironic-inspector" "baremetal-introspection" "Ironic Inspector baremetal introspection service"
    get_or_create_endpoint "baremetal-introspection" "$REGION_NAME" \
        "$IRONIC_INSPECTOR_URI" "$IRONIC_INSPECTOR_URI" "$IRONIC_INSPECTOR_URI"

    if is_dnsmasq_filter_required ; then
        configure_inspector_dnsmasq_rootwrap
        configure_inspector_pxe_filter_dnsmasq
    fi

}

function configure_inspector_swift {
    inspector_configure_auth_for swift
}

function configure_inspector_dhcp {
    mkdir_chown_stack "$IRONIC_INSPECTOR_CONF_DIR"

    if [[ "$IRONIC_IPXE_ENABLED" == "True" ]] ; then
        cat > "$IRONIC_INSPECTOR_DHCP_CONF_FILE" <<EOF
no-daemon
port=0
interface=$IRONIC_INSPECTOR_INTERFACE
bind-interfaces
dhcp-range=$IRONIC_INSPECTOR_DHCP_RANGE
dhcp-match=ipxe,175
dhcp-boot=tag:!ipxe,undionly.kpxe
dhcp-boot=tag:ipxe,http://$IRONIC_HTTP_SERVER:$IRONIC_HTTP_PORT/ironic-inspector.ipxe
dhcp-sequential-ip
EOF
    else
        cat > "$IRONIC_INSPECTOR_DHCP_CONF_FILE" <<EOF
no-daemon
port=0
interface=$IRONIC_INSPECTOR_INTERFACE
bind-interfaces
dhcp-range=$IRONIC_INSPECTOR_DHCP_RANGE
dhcp-boot=pxelinux.0
dhcp-sequential-ip
EOF
    fi

    if is_dnsmasq_filter_required ; then
        configure_dnsmasq_dhcp_hostsdir
    fi
}

function prepare_environment {
    prepare_tftp
    create_ironic_inspector_cache_dir

    if [[ "$IRONIC_BAREMETAL_BASIC_OPS" == "True" && "$IRONIC_IS_HARDWARE" == "False" ]]; then
        sudo ip link add $IRONIC_INSPECTOR_OVS_PORT type veth peer name $IRONIC_INSPECTOR_INTERFACE
        sudo ip link set dev $IRONIC_INSPECTOR_OVS_PORT up
        sudo ip link set dev $IRONIC_INSPECTOR_OVS_PORT mtu $PUBLIC_BRIDGE_MTU
        sudo ovs-vsctl add-port $IRONIC_VM_NETWORK_BRIDGE $IRONIC_INSPECTOR_OVS_PORT
    fi
    sudo ip link set dev $IRONIC_INSPECTOR_INTERFACE up
    sudo ip link set dev $IRONIC_INSPECTOR_INTERFACE mtu $PUBLIC_BRIDGE_MTU
    sudo ip addr add $IRONIC_INSPECTOR_INTERNAL_IP_WITH_NET dev $IRONIC_INSPECTOR_INTERFACE

    sudo iptables -I INPUT -i $IRONIC_INSPECTOR_INTERFACE -p udp \
        --dport 69 -j ACCEPT
    sudo iptables -I INPUT -i $IRONIC_INSPECTOR_INTERFACE -p tcp \
        --dport $IRONIC_INSPECTOR_PORT -j ACCEPT
}

# create_ironic_inspector_cache_dir() - Part of the prepare_environment() process
function create_ironic_inspector_cache_dir {
    # Create cache dir
    mkdir_chown_stack $IRONIC_INSPECTOR_AUTH_CACHE_DIR/api
    rm -f $IRONIC_INSPECTOR_AUTH_CACHE_DIR/api/*
    mkdir_chown_stack $IRONIC_INSPECTOR_AUTH_CACHE_DIR/registry
    rm -f $IRONIC_INSPECTOR_AUTH_CACHE_DIR/registry/*
}

function cleanup_inspector {
    if [[ "$IRONIC_IPXE_ENABLED" == "True" ]] ; then
        rm -f $IRONIC_HTTP_DIR/ironic-inspector.*
    else
        rm -f $IRONIC_TFTPBOOT_DIR/pxelinux.cfg/default
        rm -f $IRONIC_TFTPBOOT_DIR/ironic-inspector.*
    fi
    sudo rm -f /etc/sudoers.d/ironic-inspector-rootwrap
    sudo rm -rf $IRONIC_INSPECTOR_AUTH_CACHE_DIR
    sudo rm -rf "$IRONIC_INSPECTOR_RAMDISK_LOGDIR"

    # Always try to clean up firewall rules, no matter filter driver used
    sudo iptables -D INPUT -i $IRONIC_INSPECTOR_INTERFACE -p udp \
        --dport 69 -j ACCEPT | true
    sudo iptables -D INPUT -i $IRONIC_INSPECTOR_INTERFACE -p tcp \
        --dport $IRONIC_INSPECTOR_PORT -j ACCEPT | true
    sudo iptables -D INPUT -i $IRONIC_INSPECTOR_INTERFACE -p udp \
        --dport 67 -j ironic-inspector | true
    sudo iptables -F ironic-inspector | true
    sudo iptables -X ironic-inspector | true

    if [[ $IRONIC_INSPECTOR_INTERFACE != $OVS_PHYSICAL_BRIDGE && "$IRONIC_INSPECTOR_INTERFACE_PHYSICAL" == "False" ]]; then
        sudo ip link show $IRONIC_INSPECTOR_INTERFACE && sudo ip link delete $IRONIC_INSPECTOR_INTERFACE
    fi
    sudo ip link show $IRONIC_INSPECTOR_OVS_PORT && sudo ip link delete $IRONIC_INSPECTOR_OVS_PORT
    sudo ovs-vsctl --if-exists del-port $IRONIC_INSPECTOR_OVS_PORT
}

function sync_inspector_database {
    recreate_database ironic_inspector
    $IRONIC_INSPECTOR_DBSYNC_BIN_FILE --config-file $IRONIC_INSPECTOR_CONF_FILE upgrade
}

### Entry points

if [[ "$1" == "stack" && "$2" == "install" ]]; then
    echo_summary "Installing ironic-inspector"
    if is_inspector_dhcp_required; then
        install_inspector_dhcp
    fi
    install_inspector
    install_inspector_client
elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
    echo_summary "Configuring ironic-inspector"
    cleanup_inspector
    if is_inspector_dhcp_required; then
        configure_inspector_dhcp
    fi
    configure_inspector
    sync_inspector_database
elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
    echo_summary "Initializing ironic-inspector"
    prepare_environment
    if is_inspector_dhcp_required; then
        start_inspector_dhcp
    fi
    start_inspector
elif [[ "$1" == "stack" && "$2" == "test-config" ]]; then
    if is_service_enabled tempest; then
        echo_summary "Configuring Tempest for Ironic Inspector"
        iniset $TEMPEST_CONFIG service_available ironic_inspector True
        if [ -n "$IRONIC_INSPECTOR_NODE_NOT_FOUND_HOOK" ]; then
            iniset $TEMPEST_CONFIG baremetal_introspection auto_discovery_feature True
            iniset $TEMPEST_CONFIG baremetal_introspection auto_discovery_default_driver fake-hardware
            iniset $TEMPEST_CONFIG baremetal_introspection auto_discovery_target_driver ipmi
        fi
        iniset $TEMPEST_CONFIG baremetal_introspection data_store $IRONIC_INSPECTOR_INTROSPECTION_DATA_STORE
    fi
fi

if [[ "$1" == "unstack" ]]; then
    stop_inspector
    if is_inspector_dhcp_required; then
        stop_inspector_dhcp
    fi
    cleanup_inspector
fi
