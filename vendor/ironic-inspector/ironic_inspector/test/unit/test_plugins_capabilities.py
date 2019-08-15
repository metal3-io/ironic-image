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

import mock
from oslo_config import cfg

from ironic_inspector import node_cache
from ironic_inspector.plugins import base
from ironic_inspector.plugins import capabilities
from ironic_inspector.test import base as test_base


CONF = cfg.CONF


@mock.patch.object(node_cache.NodeInfo, 'update_capabilities', autospec=True)
class TestCapabilitiesHook(test_base.NodeTest):
    hook = capabilities.CapabilitiesHook()

    def test_loadable_by_name(self, mock_caps):
        base.CONF.set_override('processing_hooks', 'capabilities',
                               'processing')
        ext = base.processing_hooks_manager()['capabilities']
        self.assertIsInstance(ext.obj, capabilities.CapabilitiesHook)

    def test_no_data(self, mock_caps):
        self.hook.before_update(self.data, self.node_info)
        self.assertFalse(mock_caps.called)

    def test_boot_mode(self, mock_caps):
        CONF.set_override('boot_mode', True, 'capabilities')
        self.inventory['boot'] = {'current_boot_mode': 'uefi'}

        self.hook.before_update(self.data, self.node_info)
        mock_caps.assert_called_once_with(self.node_info, boot_mode='uefi')

    def test_boot_mode_disabled(self, mock_caps):
        self.inventory['boot'] = {'current_boot_mode': 'uefi'}

        self.hook.before_update(self.data, self.node_info)
        self.assertFalse(mock_caps.called)

    def test_cpu_flags(self, mock_caps):
        self.inventory['cpu']['flags'] = ['fpu', 'vmx', 'aes', 'pse', 'smx']

        self.hook.before_update(self.data, self.node_info)
        mock_caps.assert_called_once_with(self.node_info,
                                          cpu_vt='true',
                                          cpu_hugepages='true',
                                          cpu_txt='true',
                                          cpu_aes='true')

    def test_cpu_no_known_flags(self, mock_caps):
        self.inventory['cpu']['flags'] = ['fpu']

        self.hook.before_update(self.data, self.node_info)
        self.assertFalse(mock_caps.called)

    def test_cpu_flags_custom(self, mock_caps):
        CONF.set_override('cpu_flags', {'fpu': 'new_cap'},
                          'capabilities')
        self.inventory['cpu']['flags'] = ['fpu', 'vmx', 'aes', 'pse']

        self.hook.before_update(self.data, self.node_info)
        mock_caps.assert_called_once_with(self.node_info,
                                          new_cap='true')
