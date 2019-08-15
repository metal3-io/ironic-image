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

from oslo_config import cfg
from oslo_log import log

from ironic_inspector.conf import opts

LOG = log.getLogger(__name__)
CONF = cfg.CONF


def prepare_service(args=None):
    args = [] if args is None else args
    log.register_options(CONF)
    opts.set_config_defaults()
    opts.parse_args(args)
    log.setup(CONF, 'ironic_inspector')

    LOG.debug("Configuration:")
    CONF.log_opt_values(LOG, log.DEBUG)
