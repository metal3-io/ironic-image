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

import socket

from oslo_config import cfg

from ironic_inspector.common.i18n import _


_OPTS = [
    cfg.StrOpt('listen_address',
               default='0.0.0.0',
               help=_('IP to listen on.')),
    cfg.PortOpt('listen_port',
                default=5050,
                help=_('Port to listen on.')),
    cfg.StrOpt('host',
               default=socket.getfqdn(),
               sample_default='localhost',
               help=_('Name of this node. This can be an opaque identifier. '
                      'It is not necessarily a hostname, FQDN, or IP address. '
                      'However, the node name must be valid within '
                      'an AMQP key, and if using ZeroMQ, a valid '
                      'hostname, FQDN, or IP address.')),
    cfg.StrOpt('auth_strategy',
               default='keystone',
               choices=('keystone', 'noauth'),
               help=_('Authentication method used on the ironic-inspector '
                      'API. Either "noauth" or "keystone" are currently valid '
                      'options. "noauth" will disable all authentication.')),
    cfg.IntOpt('timeout',
               default=3600,
               # We're using timedelta which can overflow if somebody sets this
               # too high, so limit to a sane value of 10 years.
               max=315576000,
               help=_('Timeout after which introspection is considered '
                      'failed, set to 0 to disable.')),
    cfg.IntOpt('clean_up_period',
               default=60,
               help=_('Amount of time in seconds, after which repeat clean up '
                      'of timed out nodes and old nodes status information.')),
    cfg.BoolOpt('use_ssl',
                default=False,
                help=_('SSL Enabled/Disabled')),
    cfg.IntOpt('max_concurrency',
               default=1000, min=2,
               help=_('The green thread pool size.')),
    cfg.IntOpt('introspection_delay',
               default=5,
               help=_('Delay (in seconds) between two introspections.')),
    cfg.ListOpt('ipmi_address_fields',
                default=['ilo_address', 'drac_host', 'drac_address',
                         'cimc_address'],
                help=_('Ironic driver_info fields that are equivalent '
                       'to ipmi_address.')),
    cfg.StrOpt('rootwrap_config',
               default="/etc/ironic-inspector/rootwrap.conf",
               help=_('Path to the rootwrap configuration file to use for '
                      'running commands as root')),
    cfg.IntOpt('api_max_limit', default=1000, min=1,
               help=_('Limit the number of elements an API list-call '
                      'returns')),
    cfg.BoolOpt('can_manage_boot', default=True,
                help=_('Whether the current installation of ironic-inspector '
                       'can manage PXE booting of nodes. If set to False, '
                       'the API will reject introspection requests with '
                       'manage_boot missing or set to True.')),
    cfg.BoolOpt('enable_mdns', default=False,
                help=_('Whether to enable publishing the ironic-inspector API '
                       'endpoint via multicast DNS.')),
    cfg.BoolOpt('standalone', default=True,
                help=_('Whether to run ironic-inspector as a standalone '
                       'service. It\'s EXPERIMENTAL to set to False.'))
]


def register_opts(conf):
    conf.register_opts(_OPTS)


def list_opts():
    return _OPTS
