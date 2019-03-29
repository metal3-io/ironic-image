#!/usr/bin/bash

# mysql configuration
PATH=$PATH:/usr/sbin/
DATADIR="/var/lib/mysql"
if [ ! -f "$DATADIR/ironic-initalized" ]; then
    crudini --set /etc/my.conf mysqld max_connects 64
    crudini --set /etc/my.conf mysqld max_heap_table_size 1M
    crudini --set /etc/my.conf mysqld innodb_buffer_pool_size 5M
    crudini --set /etc/my.conf mysqld innodb_log_buffer_size 512K
    mysql_install_db --datadir=$DATADIR
    chown -R mysql /var/log/mariadb
    chown -R mysql $DATADIR
    cd /usr
    mysqld_safe --datadir=$DATADIR --user mysql &
    sleep 1
    ironic_password=$(echo $(date;hostname)|sha256sum |cut -c-20)
    mysqladmin -u root password $ironic_password
    cat > /tmp/configure-mysql.sql << EOF
TRUNCATE mysql.user;
CREATE USER 'ironic'@'localhost' identified by '$ironic_password';
GRANT ALL on *.* TO 'ironic'@'localhost' WITH GRANT OPTION;
DROP DATABASE IF EXISTS test;
CREATE DATABASE ironic;
FLUSH PRIVILEGES;
EOF
    mysql -u root -p$ironic_password -h 127.0.0.1 < /tmp/configure-mysql.sql
    ps auxf
    crudini --set /etc/ironic/ironic.conf database connection mysql+pymysql://ironic:$ironic_password@localhost/ironic?charset=utf8
    ironic-dbsync --config-file /etc/ironic/ironic.conf create_schema
    touch $DATADIR/ironic-initalized
else
    mysqld_safe --datadir=$DATADIR --user mysql &
fi

# Get environment settings and update ironic.conf
IP=${IP:-"172.22.0.1"}
HTTP_PORT=${HTTP_PORT:-"80"}
INTERFACE=${INTERFACE:-"provisioning"}

sed -i -e s/IRONIC_IP/$IP/g -e s/HTTP_PORT/$HTTP_PORT/g /etc/ironic/ironic.conf 

# Allow access to Ironic
if ! iptables -C INPUT -i $INTERFACE -p tcp -m tcp --dport 5050 -j ACCEPT > /dev/null 2>&1; then
    iptables -I INPUT -i $INTERFACE -p tcp -m tcp --dport 5050 -j ACCEPT
fi

/usr/bin/python2 /usr/bin/ironic-conductor > /var/log/ironic-conductor.out 2>&1 &

/usr/bin/python2 /usr/bin/ironic-api > /var/log/ironic-api.out 2>&1 &
/bin/runhealthcheck "ironic" &>/dev/null &
sleep infinity

