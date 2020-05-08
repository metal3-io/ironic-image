#!/usr/bin/bash

. /bin/configure-ironic.sh

# Wait for ironic to load all expected drivers
# the DB query returns a string like ["fake-hardware", "idrac", "ipmi"]
DB_DRIVERS=$(mysql --user=ironic --password=${MARIADB_PASSWORD} --protocol=tcp -r -s -e "use ironic; select drivers from conductors;" | grep -oE '"[^"]+"' | wc -l)
CONF_DRIVERS=$(crudini --get /etc/ironic/ironic.conf DEFAULT enabled_hardware_types | tr ',' '\n' | wc -l)
while [ $DB_DRIVERS -lt $CONF_DRIVERS ]; do
  echo "Waiting for expected drivers $CONF_DRIVERS from conductor"
  sleep 5
  DB_DRIVERS=$(mysql --user=ironic --password=${MARIADB_PASSWORD} --protocol=tcp -r -s -e "use ironic; select drivers from conductors;" | grep -oE '"[^"]+"' | wc -l)
done

exec /usr/bin/ironic-api --config-file /etc/ironic/ironic.conf
