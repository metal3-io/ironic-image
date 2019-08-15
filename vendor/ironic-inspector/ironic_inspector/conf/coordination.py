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


# NOTE(kaifeng) The capability of various backend varies, please check tooz
# documentation for driver compatibilities:
# https://docs.openstack.org/tooz/latest/user/compatibility.html
_OPTS = [
    cfg.StrOpt('backend_url',
               default='memcached://localhost:11211',
               help=_('The backend URL to use for distributed coordination. '
                      'EXPERIMENTAL.')),
]


def register_opts(conf):
    conf.register_opts(_OPTS, 'coordination')


def list_opts():
    return _OPTS
