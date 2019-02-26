#!/bin/bash
set -ex

trap killcontainer ERR
function killcontainer(){
    killall -9 sleep
}

while true ; do
    sleep 10

    HTTPDPID=$(pidof -s httpd)
    fuser 80/tcp |& grep -w "$HTTPDPID"

    DNSMASQPID=$(pidof dnsmasq)
    fuser 69/udp |& grep -w "$DNSMASQPID"

    curl -s http://172.22.0.1:6385 > /dev/null || ( echo "Can't contact ironic-api" && exit 1 )

done
