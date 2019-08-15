# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_config import cfg
from oslo_log import log
from oslo_service import service

from ironic_inspector.common import rpc
from ironic_inspector.conductor import manager

CONF = cfg.CONF
LOG = log.getLogger(__name__)

SERVER_NAME = 'ironic-inspector-rpc-server'


class RPCService(service.Service):

    def __init__(self, host):
        super(RPCService, self).__init__()
        self.host = host
        self.manager = manager.ConductorManager()
        self.rpcserver = None

    def start(self):
        super(RPCService, self).start()
        self.rpcserver = rpc.get_server([self.manager])
        self.rpcserver.start()

        self.manager.init_host()
        LOG.info('Created RPC server for service %(service)s on host '
                 '%(host)s.',
                 {'service': manager.MANAGER_TOPIC, 'host': self.host})

    def stop(self):
        try:
            self.rpcserver.stop()
            self.rpcserver.wait()
        except Exception as e:
            LOG.exception('Service error occurred when stopping the '
                          'RPC server. Error: %s', e)

        try:
            self.manager.del_host()
        except Exception as e:
            LOG.exception('Service error occurred when cleaning up '
                          'the RPC manager. Error: %s', e)

        super(RPCService, self).stop(graceful=True)
        LOG.info('Stopped RPC server for service %(service)s on host '
                 '%(host)s.',
                 {'service': manager.MANAGER_TOPIC, 'host': self.host})
