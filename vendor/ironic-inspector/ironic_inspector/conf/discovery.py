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
    cfg.StrOpt('enroll_node_driver',
               default='fake-hardware',
               help=_('The name of the Ironic driver used by the enroll '
                      'hook when creating a new node in Ironic.')),
    cfg.ListOpt('enabled_bmc_address_version',
                default=['4', '6'],
                help=_('IP version of BMC address that will be '
                       'used when enrolling a new node in Ironic. '
                       'Defaults to "4,6". Could be "4" (use v4 address '
                       'only), "4,6" (v4 address have higher priority and '
                       'if both addresses found v6 version is ignored), '
                       '"6,4" (v6 is desired but fall back to v4 address '
                       'for BMCs having v4 address, opposite to "4,6"), '
                       '"6" (use v6 address only and ignore v4 version).')),
]


def register_opts(conf):
    conf.register_opts(_OPTS, 'discovery')


def list_opts():
    return _OPTS
