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
from oslo_service import service
from oslo_service import wsgi

from ironic_inspector import main as app
from ironic_inspector import utils

LOG = log.getLogger(__name__)
CONF = cfg.CONF


class WSGIService(service.Service):
    """Provides ability to launch API from wsgi app."""

    def __init__(self):
        self.app = app.app
        self.server = wsgi.Server(CONF, 'ironic_inspector',
                                  self.app,
                                  host=CONF.listen_address,
                                  port=CONF.listen_port,
                                  use_ssl=CONF.use_ssl)

    def _init_middleware(self):
        """Initialize WSGI middleware.

        :returns: None
        """
        if CONF.auth_strategy != 'noauth':
            utils.add_auth_middleware(self.app)
        else:
            LOG.warning('Starting unauthenticated, please check'
                        ' configuration')
        utils.add_cors_middleware(self.app)

    def start(self):
        """Start serving this service using loaded configuration.

        :returns: None
        """
        self._init_middleware()
        self.server.start()

    def stop(self):
        """Stop serving this API.

        :returns: None
        """
        self.server.stop()

    def wait(self):
        """Wait for the service to stop serving this API.

        :returns: None
        """
        self.server.wait()

    def reset(self):
        """Reset server greenpool size to default.

        :returns: None
        """
        self.server.reset()
