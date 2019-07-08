#!/usr/bin/bash

. /bin/configure-ironic.sh

# TODO(dtantsur): merge these two scripts when/if we no longer support
# all-in-one container
/bin/runexporterapp
