#!/bin/bash
set -ex

trap killcontainer ERR
function killcontainer(){
    killall -9 sleep
}

while true ; do
    sleep 30

    if [ $1 = "httpd" ] ; then
       HTTPDPID=$(pidof -s httpd)
       fuser $2/tcp |& grep -w "$HTTPDPID"

    elif [ $1 = "dnsmasq" ] ; then
       DNSMASQPID=$(pidof dnsmasq)
       fuser 67/udp 547/udp |& grep -w "$DNSMASQPID"

    elif [ $1 = "ironic" ] ; then
       curl -s http://localhost:6385 > /dev/null || ( echo "Can't contact ironic-api" && exit 1 )
    fi

done
