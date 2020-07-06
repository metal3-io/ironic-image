#!/usr/bin/bash

. /bin/configure-ironic.sh

# Remove log files from last deployment
rm -rf /shared/log/ironic
mkdir -p /shared/log/ironic

if [ ! -z "$CLIENT_CERT_FILE" ] || [ ! -z "$CLIENT_KEY_FILE" ] || [ ! -z "$CACERT_FILE" ] || [ ! -z "$INSECURE" ]; then
    crudini --merge /etc/ironic/ironic.conf <<EOF
[json_rpc]
use_ssl = true
$([ ! -z "$CLIENT_CERT_FILE" ] && echo "certfile = $CLIENT_CERT_FILE")
$([ ! -z "$CLIENT_KEY_FILE" ] && echo "keyfile = $CLIENT_KEY_FILE")
$([ ! -z "$CACERT_FILE" ] && echo "cafile = $CACERT_FILE")
$([ ! -z "$INSECURE" ] && echo "insecure = $INSECURE" || echo "insecure = false")
port = 8089
EOF
else
    crudini --merge /etc/ironic/ironic.conf <<EOF
[json_rpc]
port = 8089
use_ssl = false
EOF
fi

# Template and write httpd ironic.conf
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < /etc/httpd-ironic-api.conf.j2 > /etc/httpd/conf.d/ironic-api.conf
sed -i "/Listen 80/c\#Listen 80" /etc/httpd/conf/httpd.conf

exec /usr/sbin/httpd -DFOREGROUND
