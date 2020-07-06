#!/usr/bin/bash

. /bin/configure-ironic.sh

/bin/runironic-conductor &
/bin/runironic-api &

sleep infinity

