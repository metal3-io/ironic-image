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

from ironic_inspector import node_cache
from ironic_inspector.plugins import base
from ironic_inspector.plugins import pci_devices
from ironic_inspector.test import base as test_base


class TestPciDevicesHook(test_base.NodeTest):
    hook = pci_devices.PciDevicesHook()

    def test_parse_pci_alias_entry(self):
        pci_alias = ['{"vendor_id": "foo1", "product_id": "bar1",'
                     ' "name": "baz1"}',
                     '{"vendor_id": "foo2", "product_id": "bar2",'
                     ' "name": "baz2"}']
        valid_pci_entry = {("foo1", "bar1"): "baz1", ("foo2", "bar2"): "baz2"}
        base.CONF.set_override('alias', pci_alias, 'pci_devices')
        parsed_pci_entry = pci_devices._parse_pci_alias_entry()
        self.assertEqual(valid_pci_entry, parsed_pci_entry)

    def test_parse_pci_alias_entry_no_entries(self):
        pci_alias = []
        base.CONF.set_override('alias', pci_alias, 'pci_devices')
        parsed_pci_alias = pci_devices._parse_pci_alias_entry()
        self.assertFalse(parsed_pci_alias)

    @mock.patch('ironic_inspector.plugins.pci_devices.LOG')
    def test_parse_pci_alias_entry_invalid_json(self, mock_oslo_log):
        pci_alias = ['{"vendor_id": "foo1", "product_id": "bar1",'
                     ' "name": "baz1"}', '{"invalid" = "entry"}']
        base.CONF.set_override('alias', pci_alias, 'pci_devices')
        valid_pci_alias = {("foo1", "bar1"): "baz1"}
        parsed_pci_alias = pci_devices._parse_pci_alias_entry()
        self.assertEqual(valid_pci_alias, parsed_pci_alias)
        mock_oslo_log.error.assert_called_once()

    @mock.patch('ironic_inspector.plugins.pci_devices.LOG')
    def test_parse_pci_alias_entry_invalid_keys(self, mock_oslo_log):
        pci_alias = ['{"vendor_id": "foo1", "product_id": "bar1",'
                     ' "name": "baz1"}', '{"invalid": "keys"}']
        base.CONF.set_override('alias', pci_alias, 'pci_devices')
        valid_pci_alias = {("foo1", "bar1"): "baz1"}
        parsed_pci_alias = pci_devices._parse_pci_alias_entry()
        self.assertEqual(valid_pci_alias, parsed_pci_alias)
        mock_oslo_log.error.assert_called_once()

    @mock.patch.object(hook, 'aliases', {("1234", "5678"): "pci_dev1",
                                         ("9876", "5432"): "pci_dev2"})
    @mock.patch.object(node_cache.NodeInfo, 'update_capabilities',
                       autospec=True)
    def test_before_update(self, mock_update_props):
        self.data['pci_devices'] = [
            {"vendor_id": "1234", "product_id": "5678"},
            {"vendor_id": "1234", "product_id": "5678"},
            {"vendor_id": "1234", "product_id": "7890"},
            {"vendor_id": "9876", "product_id": "5432"}
        ]
        expected_pci_devices_count = {"pci_dev1": 2, "pci_dev2": 1}
        self.hook.before_update(self.data, self.node_info)
        mock_update_props.assert_called_once_with(self.node_info,
                                                  **expected_pci_devices_count)

    @mock.patch('ironic_inspector.plugins.pci_devices.LOG')
    @mock.patch.object(node_cache.NodeInfo, 'update_capabilities',
                       autospec=True)
    def test_before_update_no_pci_info_from_ipa(self, mock_update_props,
                                                mock_oslo_log):
        pci_alias = ['{"vendor_id": "foo1", "product_id": "bar1",'
                     ' "name": "baz1"}']
        base.CONF.set_override('alias', pci_alias, 'pci_devices')
        self.hook.before_update(self.data, self.node_info)
        mock_oslo_log.warning.assert_called_once()
        self.assertFalse(mock_update_props.called)

    @mock.patch.object(pci_devices, '_parse_pci_alias_entry')
    @mock.patch('ironic_inspector.plugins.pci_devices.LOG')
    @mock.patch.object(node_cache.NodeInfo, 'update_capabilities',
                       autospec=True)
    def test_before_update_no_match(self, mock_update_props, mock_oslo_log,
                                    mock_parse_pci_alias):
        self.data['pci_devices'] = [
            {"vendor_id": "1234", "product_id": "5678"},
            {"vendor_id": "1234", "product_id": "7890"},
        ]
        mock_parse_pci_alias.return_value = {("9876", "5432"): "pci_dev"}
        self.hook.before_update(self.data, self.node_info)
        self.assertFalse(mock_update_props.called)
        self.assertFalse(mock_oslo_log.info.called)
