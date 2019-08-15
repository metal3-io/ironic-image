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


DEFAULT_CPU_FLAGS_MAPPING = {
    'vmx': 'cpu_vt',
    'svm': 'cpu_vt',
    'aes': 'cpu_aes',
    'pse': 'cpu_hugepages',
    'pdpe1gb': 'cpu_hugepages_1g',
    'smx': 'cpu_txt',
}


_OPTS = [
    cfg.BoolOpt('boot_mode',
                default=False,
                help=_('Whether to store the boot mode (BIOS or UEFI).')),
    cfg.DictOpt('cpu_flags',
                default=DEFAULT_CPU_FLAGS_MAPPING,
                help=_('Mapping between a CPU flag and a capability to set '
                       'if this flag is present.')),
]


def register_opts(conf):
    conf.register_opts(_OPTS, 'capabilities')


def list_opts():
    return _OPTS
