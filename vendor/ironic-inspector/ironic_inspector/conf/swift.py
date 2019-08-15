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
from ironic_inspector.common import keystone


SWIFT_GROUP = 'swift'
SERVICE_TYPE = 'object-store'


_OPTS = [
    cfg.IntOpt('max_retries',
               help=_('This option is deprecated and has no effect.'),
               deprecated_for_removal=True),
    cfg.IntOpt('delete_after',
               default=0,
               help=_('Number of seconds that the Swift object will last '
                      'before being deleted. (set to 0 to never delete the '
                      'object).')),
    cfg.StrOpt('container',
               default='ironic-inspector',
               help=_('Default Swift container to use when creating '
                      'objects.')),
]


def register_opts(conf):
    conf.register_opts(_OPTS, SWIFT_GROUP)
    keystone.register_auth_opts(SWIFT_GROUP, SERVICE_TYPE)


def list_opts():
    return keystone.add_auth_options(_OPTS, SERVICE_TYPE)
