#!/usr/bin/bash

rmdir /var/www/html
ln -s /shared/html/ /var/www/html

/usr/sbin/httpd &
/bin/runhealthcheck "httpd" &2>/dev/null &
sleep infinity

