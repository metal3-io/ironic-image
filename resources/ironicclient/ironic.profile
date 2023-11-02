REQUESTS_CA_BUNDLE=/proc/1/root/certs/ca/ironic-inspector/ca.crt
OS_AUTH_TYPE=none
OS_ENDPOINT="$(grep endpoint_override /proc/1/root/etc/ironic/ironic.conf|grep 6385|cut -d\  -f3)"
export REQUESTS_CA_BUNDLE OS_AUTH_TYPE OS_ENDPOINT
