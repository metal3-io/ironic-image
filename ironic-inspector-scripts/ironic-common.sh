export PROVISIONING_INTERFACE=${PROVISIONING_INTERFACE:-"provisioning"}

# Wait for the interface or IP to be up, sets $IRONIC_IP
function get_ironic_ip() {
  # If $PROVISIONING_IP is specified, then we wait for that to become available on an interface, otherwise we look at $PROVISIONING_INTERFACE for an IP
  if [ ! -z "${PROVISIONING_IP}" ];
  then
    local prov_ip=$(printf %s "${PROVISIONING_IP}" | sed -e 's%/.*%%')
    echo "Waiting for ${prov_ip} to be configured on an interface"
    if ip -br addr show | grep -q -F " ${prov_ip}/"; then
      export IRONIC_IP="${prov_ip}"
    fi
  else
    echo "Waiting for ${PROVISIONING_INTERFACE} interface to be configured"
    export IRONIC_IP=$(ip -br add show scope global up dev "${PROVISIONING_INTERFACE}" | awk '{print $3}' | sed -e 's%/.*%%' | head -n 1)
  fi

  if [ ! -z "${IRONIC_IP}" ]; then
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
  fi
}

function wait_for_interface_or_ip() {
  export IRONIC_IP=""
  until [ ! -z "${IRONIC_IP}" ]; do
    get_ironic_ip
    sleep 1
  done
}
