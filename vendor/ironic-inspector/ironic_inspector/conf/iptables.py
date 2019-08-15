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
    cfg.StrOpt('dnsmasq_interface',
               default='br-ctlplane',
               help=_('Interface on which dnsmasq listens, the default is for '
                      'VM\'s.')),
    cfg.StrOpt('firewall_chain',
               default='ironic-inspector',
               help=_('iptables chain name to use.')),
    cfg.ListOpt('ethoib_interfaces',
                default=[],
                help=_('List of Etherent Over InfiniBand interfaces '
                       'on the Inspector host which are used for physical '
                       'access to the DHCP network. Multiple interfaces would '
                       'be attached to a bond or bridge specified in '
                       'dnsmasq_interface. The MACs of the InfiniBand nodes '
                       'which are not in desired state are going to be '
                       'blacklisted based on the list of neighbor MACs '
                       'on these interfaces.')),
    cfg.StrOpt('ip_version',
               default='4',
               choices=[('4', _('IPv4')),
                        ('6', _('IPv6'))],
               help=_('The IP version that will be used for iptables filter. '
                      'Defaults to 4.')),
]


def register_opts(conf):
    conf.register_opts(_OPTS, 'iptables')


def list_opts():
    return _OPTS
