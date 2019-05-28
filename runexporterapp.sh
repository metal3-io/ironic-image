#!/usr/bin/bash

cd /ironic-prometheus-exporter
export IRONIC_CONFIG=/etc/ironic/ironic.conf
export FLASK_RUN_HOST=0.0.0.0
export FLASK_RUN_PORT=5001
uwsgi --socket ${FLASK_RUN_HOST}:${FLASK_RUN_PORT} --protocol=http -w ironic_prometheus_exporter.app.wsgi
