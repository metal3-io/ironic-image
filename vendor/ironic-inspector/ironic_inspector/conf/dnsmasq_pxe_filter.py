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

from ironic_inspector.common.i18n import _


_OPTS = [
    cfg.StrOpt('dhcp_hostsdir',
               default='/var/lib/ironic-inspector/dhcp-hostsdir',
               help=_('The MAC address cache directory, exposed to dnsmasq.'
                      'This directory is expected to be in exclusive control '
                      'of the driver.')),
    cfg.BoolOpt('purge_dhcp_hostsdir', default=True,
                help=_('Purge the hostsdir upon driver initialization. '
                       'Setting to false should only be performed when the '
                       'deployment of inspector is such that there are '
                       'multiple processes executing inside of the same host '
                       'and namespace. In this case, the Operator is '
                       'responsible for setting up a custom cleaning '
                       'facility.')),
    cfg.StrOpt('dnsmasq_start_command', default='',
               help=_('A (shell) command line to start the dnsmasq service '
                      'upon filter initialization. Default: don\'t start.')),
    cfg.StrOpt('dnsmasq_stop_command', default='',
               help=_('A (shell) command line to stop the dnsmasq service '
                      'upon inspector (error) exit. Default: don\'t stop.')),

]


def register_opts(conf):
    conf.register_opts(_OPTS, 'dnsmasq_pxe_filter')


def list_opts():
    return _OPTS
