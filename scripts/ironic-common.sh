function get_provisioning_interface() {
  if [ -n "${PROVISIONING_INTERFACE}" ]; then
    # don't override the PROVISIONING_INTERFACE if one is provided
    echo ${PROVISIONING_INTERFACE}
    return
  fi

  local interface="provisioning"
  for mac in ${PROVISIONING_MACS//,/ } ; do
    if ip -br link show up | grep -qi "$mac"; then
      interface=$(ip -br link show up | grep -i "$mac" | cut -f 1 -d ' ')
      break
    fi
  done
  echo $interface
}

export PROVISIONING_INTERFACE=$(get_provisioning_interface)

export LISTEN_ALL_INTERFACES="${LISTEN_ALL_INTERFACES:-"true"}"

# Wait for the interface or IP to be up, sets $IRONIC_IP
function wait_for_interface_or_ip() {
  # If $PROVISIONING_IP is specified, then we wait for that to become available on an interface, otherwise we look at $PROVISIONING_INTERFACE for an IP
  if [ ! -z "${PROVISIONING_IP}" ];
  then
    # Convert the address using ipcalc which strips out the subnet. For IPv6 addresses, this will give the short-form address
    export IRONIC_IP=$(ipcalc "${PROVISIONING_IP}" | grep "^Address:" | awk '{print $2}')
    until ip -br addr show | grep -q -F " ${IRONIC_IP}/"; do
      echo "Waiting for ${IRONIC_IP} to be configured on an interface"
      sleep 1
    done
  else
    until [ ! -z "${IRONIC_IP}" ]; do
      echo "Waiting for ${PROVISIONING_INTERFACE} interface to be configured"
      export IRONIC_IP=$(ip -br add show scope global up dev "${PROVISIONING_INTERFACE}" | awk '{print $3}' | sed -e 's%/.*%%' | head -n 1)
      sleep 1
    done
  fi

  # If the IP contains a colon, then it's an IPv6 address, and the HTTP
  # host needs surrounding with brackets
  if [[ "$IRONIC_IP" =~ .*:.* ]]
  then
    export IPV=6
    export IRONIC_URL_HOST="[$IRONIC_IP]"
  else
    export IPV=4
    export IRONIC_URL_HOST=$IRONIC_IP
  fi
}

function render_j2_config () {
    python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < $1 > $2
}

function run_ironic_dbsync() {
    if [[ "${IRONIC_USE_MARIADB:-true}" == "true" ]]; then
        # It's possible for the dbsync to fail if mariadb is not up yet, so
        # retry until success
        until ironic-dbsync --config-file /etc/ironic/ironic.conf upgrade; do
          echo "WARNING: ironic-dbsync failed, retrying"
          sleep 1
        done
    else
        # SQLite does not support some statements. Fortunately, we can just create
        # the schema in one go instead of going through an upgrade.
        ironic-dbsync --config-file /etc/ironic/ironic.conf create_schema
    fi
}

# Use the special value "unix" for unix sockets
export IRONIC_PRIVATE_PORT=${IRONIC_PRIVATE_PORT:-6388}
export IRONIC_INSPECTOR_PRIVATE_PORT=${IRONIC_INSPECTOR_PRIVATE_PORT:-5049}

export IRONIC_ACCESS_PORT=${IRONIC_ACCESS_PORT:-6385}
export IRONIC_LISTEN_PORT=${IRONIC_LISTEN_PORT:-$IRONIC_ACCESS_PORT}

export IRONIC_INSPECTOR_ACCESS_PORT=${IRONIC_INSPECTOR_ACCESS_PORT:-5050}
export IRONIC_INSPECTOR_LISTEN_PORT=${IRONIC_INSPECTOR_LISTEN_PORT:-$IRONIC_INSPECTOR_ACCESS_PORT}
