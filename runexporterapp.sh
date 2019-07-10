#!/usr/bin/bash

export IRONIC_CONFIG=/etc/ironic/ironic.conf
export FLASK_RUN_HOST=0.0.0.0
export FLASK_RUN_PORT=9608
uwsgi --plugin python --http-socket ${FLASK_RUN_HOST}:${FLASK_RUN_PORT} --module ironic_prometheus_exporter.app.wsgi:application
