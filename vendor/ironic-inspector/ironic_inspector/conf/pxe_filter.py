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
    cfg.StrOpt('driver', default='iptables',
               help=_('PXE boot filter driver to use, possible filters are: '
                      '"iptables", "dnsmasq" and "noop". Set "noop " to '
                      'disable the firewall filtering.')),
    cfg.IntOpt('sync_period', default=15, min=0,
               help=_('Amount of time in seconds, after which repeat periodic '
                      'update of the filter.')),
]


def register_opts(conf):
    conf.register_opts(_OPTS, 'pxe_filter')


def list_opts():
    return _OPTS
