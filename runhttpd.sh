#!/usr/bin/bash

HTTP_PORT=${HTTP_PORT:-"80"}

rmdir /var/www/html
ln -s /shared/html/ /var/www/html

sed -i 's/^Listen .*$/Listen '"$HTTP_PORT"'/' /etc/httpd/conf/httpd.conf

# Allow external access
if ! iptables -C INPUT -p tcp --dport $HTTP_PORT -j ACCEPT 2>/dev/null ; then
    iptables -I INPUT -p tcp --dport $HTTP_PORT -j ACCEPT
fi

/usr/sbin/httpd &

/bin/runhealthcheck "httpd" $HTTP_PORT &>/dev/null &
sleep infinity

