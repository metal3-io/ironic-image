#!/usr/bin/bash

export IRONIC_DEPLOYMENT="API"

. /bin/configure-ironic.sh

export IRONIC_REVERSE_PROXY_SETUP=false

python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < /etc/httpd-ironic-api.conf.j2 > /etc/httpd/conf.d/ironic.conf

. /bin/runhttpd

