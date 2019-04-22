#!/usr/bin/bash
PATH=$PATH:/usr/sbin/
DATADIR="/var/lib/mysql"
MARIADB_PASSWORD=${MARIADB_PASSWORD:-"change_me"}
MARIADB_CONF_FILE="/etc/my.cnf.d/mariadb-server.cnf"

if [ ! -d "${DATADIR}/mysql" ]; then
    crudini --set "$MARIADB_CONF_FILE" mysqld max_connections 64
    crudini --set "$MARIADB_CONF_FILE" mysqld max_heap_table_size 1M
    crudini --set "$MARIADB_CONF_FILE" mysqld innodb_buffer_pool_size 5M
    crudini --set "$MARIADB_CONF_FILE" mysqld innodb_log_buffer_size 512K
    crudini --set "$MARIADB_CONF_FILE" mysqld general_log_file /shared/log/mariadb/mariadb.log

    mysql_install_db --datadir="$DATADIR"

    mkdir -p /shared/log/mariadb
    touch /shared/log/mariadb/mariadb.log
    chmod 664 /shared/log/mariadb/mariadb.log
    chown -R mysql /shared/log/mariadb

    sed -i 's/var\/log\/mariadb\/mariadb\.log/shared\/log\/mariadb\/mariadb\.log/g' \
          /etc/my.cnf.d/mariadb-server.cnf 

    chown -R mysql "$DATADIR"

    cat > /tmp/configure-mysql.sql <<-EOSQL
DELETE FROM mysql.user ;
CREATE USER 'ironic'@'localhost' identified by '${MARIADB_PASSWORD}' ;
GRANT ALL on *.* TO 'ironic'@'localhost' WITH GRANT OPTION ;
DROP DATABASE IF EXISTS test ;
CREATE DATABASE IF NOT EXISTS  ironic ;
FLUSH PRIVILEGES ;
EOSQL

    exec mysqld_safe --init-file /tmp/configure-mysql.sql
else
    exec mysqld_safe
fi

