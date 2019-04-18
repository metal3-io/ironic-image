#!/bin/bash
set -xe

echo "*** Wait for services to come up..."
docker run --net host -e TARGETS=127.0.0.1:3306,127.0.0.1:6385,127.0.0.1:80 -e TIMEOUT=60 waisbrot/wait

echo "*** Checking containers are running..."
for CONTAINER in mariadb ironic httpd dnsmasq
do
  RESULT=$(docker inspect -f "{{.State.Running}}" $CONTAINER)
  if [ "$RESULT" != "true" ]
  then
    docker logs $CONTAINER
    echo "$CONTAINER is not running."
    exit 1
  fi
done

echo "*** Checking that ironic is responding..."
curl 'http://localhost:6385/v1/nodes'

echo "*** Checking that conductor is up..."
DRIVER_COUNT=$(curl http://localhost:6385/v1/drivers | jq '.drivers | length')
[ "$DRIVER_COUNT" -gt "0" ] || (echo "Ironic is reporting no drivers." && false)

echo "*** Checking that httpd is serving files..."
curl -I http://localhost/inspector.ipxe

echo "Success!"
