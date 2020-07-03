#!/usr/bin/bash

. /bin/configure-ironic.sh

# Template and write httpd ironic.conf
python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < /etc/httpd-ironic.conf.j2 > /etc/httpd/conf.d/ironic.conf
sed -i "/Listen 80/c\#Listen 80" /etc/httpd/conf/httpd.conf

if [ -n "${CERT_FILE}" ]; then
    inotifywait -m -e delete_self "${CERT_FILE}" | while read file event; do
        /usr/sbin/httpd -k graceful
    done &
fi

exec /usr/sbin/httpd -DFOREGROUND
