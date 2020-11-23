export PROVISIONING_INTERFACE=${PROVISIONING_INTERFACE:-"provisioning"}

# Wait for the interface or IP to be up, sets $IRONIC_IP
function wait_for_interface_or_ip() {
  # If $PROVISIONING_IP is specified, then we wait for that to become available on an interface, otherwise we look at $PROVISIONING_INTERFACE for an IP
  if [ ! -z "${PROVISIONING_IP}" ];
  then
    export IRONIC_IP=""
    until [ ! -z "${IRONIC_IP}" ]; do
      echo "Waiting for ${PROVISIONING_IP} to be configured on an interface"
      export IRONIC_IP=$(ip -br addr show | grep "${PROVISIONING_IP}" | grep -Po "[^\s]+/[0-9]+" | sed -e 's%/.*%%' | head -n 1)
      sleep 1
    done
    # When an interface has multiple IP addresses, having IRONIC_IP set at this point means that the desired provisioning ip is set on the
    # interface. However, the address returned might not be the desired one (no control over the order), so setting it back to the
    # desired IP
    if [ ! -z "${IRONIC_IP}" ]; then
      export IRONIC_IP="$(echo ${PROVISIONING_IP} | sed -e 's%/.*%%' )"
    fi
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
