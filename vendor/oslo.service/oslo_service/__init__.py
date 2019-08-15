# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os

import eventlet.patcher
from oslo_log import log as logging

time = eventlet.patcher.original('time')


LOG = logging.getLogger(__name__)

# TODO(bnemec): When we have a minimum dependency on a version of eventlet
# that uses monotonic by default, remove this monkey patching.
if hasattr(time, 'monotonic'):
    # Use builtin monotonic clock, Python 3.3+
    _monotonic = time.monotonic
else:
    import monotonic
    _monotonic = monotonic.monotonic


def service_hub():
    # NOTE(dims): Add a custom impl for EVENTLET_HUB, so we can
    # override the clock used in the eventlet hubs. The default
    # uses time.time() and we need to use a monotonic timer
    # to ensure that things like loopingcall work properly.
    hub = eventlet.hubs.get_default_hub().Hub()
    hub.clock = _monotonic
    return hub


os.environ['EVENTLET_HUB'] = 'oslo_service:service_hub'
