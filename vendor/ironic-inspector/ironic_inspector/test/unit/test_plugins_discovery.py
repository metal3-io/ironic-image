# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy

import mock

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import node_cache
from ironic_inspector.plugins import discovery
from ironic_inspector.test import base as test_base
from ironic_inspector import utils


def copy_call_args(mock_arg):
    new_mock = mock.Mock()

    def side_effect(*args, **kwargs):
        args = copy.deepcopy(args)
        kwargs = copy.deepcopy(kwargs)
        new_mock(*args, **kwargs)
        return mock.DEFAULT
    mock_arg.side_effect = side_effect
    return new_mock


class TestEnrollNodeNotFoundHook(test_base.NodeTest):
    def setUp(self):
        super(TestEnrollNodeNotFoundHook, self).setUp()
        self.ironic = mock.MagicMock()

    @mock.patch.object(node_cache, 'create_node', autospec=True)
    @mock.patch.object(ir_utils, 'get_client', autospec=True)
    @mock.patch.object(discovery, '_check_existing_nodes', autospec=True)
    def test_enroll_default(self, mock_check_existing, mock_client,
                            mock_create_node):
        mock_client.return_value = self.ironic
        introspection_data = {'test': 'test'}

        discovery.enroll_node_not_found_hook(introspection_data)

        mock_create_node.assert_called_once_with('fake-hardware',
                                                 ironic=self.ironic,
                                                 driver_info={})
        mock_check_existing.assert_called_once_with(
            introspection_data, {}, self.ironic)

    @mock.patch.object(node_cache, 'create_node', autospec=True)
    @mock.patch.object(ir_utils, 'get_client', autospec=True)
    @mock.patch.object(discovery, '_check_existing_nodes', autospec=True)
    def test_enroll_with_ipmi_address(self, mock_check_existing, mock_client,
                                      mock_create_node):
        mock_client.return_value = self.ironic
        expected_data = copy.deepcopy(self.data)
        mock_check_existing = copy_call_args(mock_check_existing)

        discovery.enroll_node_not_found_hook(self.data)

        mock_create_node.assert_called_once_with(
            'fake-hardware', ironic=self.ironic,
            driver_info={'ipmi_address': self.bmc_address})
        mock_check_existing.assert_called_once_with(
            expected_data, {'ipmi_address': self.bmc_address}, self.ironic)
        self.assertTrue(self.data['auto_discovered'])

    @mock.patch.object(node_cache, 'create_node', autospec=True)
    @mock.patch.object(ir_utils, 'get_client', autospec=True)
    @mock.patch.object(discovery, '_check_existing_nodes', autospec=True)
    def test_enroll_with_ipmi_v6address(self, mock_check_existing, mock_client,
                                        mock_create_node):
        mock_client.return_value = self.ironic
        # By default enabled_bmc_address_version="4,6".
        # Because bmc_address is not set (pop it) _extract_node_driver_info
        # method returns bmc_v6address
        self.data['inventory'].pop('bmc_address')
        expected_data = copy.deepcopy(self.data)
        mock_check_existing = copy_call_args(mock_check_existing)

        discovery.enroll_node_not_found_hook(self.data)

        mock_create_node.assert_called_once_with(
            'fake-hardware', ironic=self.ironic,
            driver_info={'ipmi_address': self.bmc_v6address})
        mock_check_existing.assert_called_once_with(
            expected_data, {'ipmi_address': self.bmc_v6address}, self.ironic)
        self.assertTrue(self.data['auto_discovered'])

    @mock.patch.object(node_cache, 'create_node', autospec=True)
    @mock.patch.object(ir_utils, 'get_client', autospec=True)
    @mock.patch.object(discovery, '_check_existing_nodes', autospec=True)
    def test_enroll_with_non_default_driver(self, mock_check_existing,
                                            mock_client, mock_create_node):
        mock_client.return_value = self.ironic
        discovery.CONF.set_override('enroll_node_driver', 'fake2',
                                    'discovery')
        mock_check_existing = copy_call_args(mock_check_existing)
        introspection_data = {}

        discovery.enroll_node_not_found_hook(introspection_data)

        mock_create_node.assert_called_once_with('fake2', ironic=self.ironic,
                                                 driver_info={})
        mock_check_existing.assert_called_once_with(
            {}, {}, self.ironic)
        self.assertEqual({'auto_discovered': True}, introspection_data)

    def test__check_existing_nodes_new_mac(self):
        self.ironic.port.list.return_value = []
        introspection_data = {'macs': self.macs}
        node_driver_info = {}

        discovery._check_existing_nodes(
            introspection_data, node_driver_info, self.ironic)

    def test__check_existing_nodes_existing_mac(self):
        self.ironic.port.list.return_value = [mock.MagicMock(
            address=self.macs[0], uuid='fake_port')]
        introspection_data = {
            'all_interfaces': {'eth%d' % i: {'mac': m}
                               for i, m in enumerate(self.macs)}
        }
        node_driver_info = {}

        self.assertRaises(utils.Error,
                          discovery._check_existing_nodes,
                          introspection_data, node_driver_info, self.ironic)

    def test__check_existing_nodes_new_node(self):
        self.ironic.node.list.return_value = [mock.MagicMock(
            driver_info={'ipmi_address': '1.2.4.3'}, uuid='fake_node')]
        introspection_data = {}
        node_driver_info = {'ipmi_address': self.bmc_address}

        discovery._check_existing_nodes(introspection_data, node_driver_info,
                                        self.ironic)

    def test__check_existing_nodes_existing_node(self):
        self.ironic.node.list.return_value = [mock.MagicMock(
            driver_info={'ipmi_address': self.bmc_address}, uuid='fake_node')]
        introspection_data = {}
        node_driver_info = {'ipmi_address': self.bmc_address}

        self.assertRaises(utils.Error, discovery._check_existing_nodes,
                          introspection_data, node_driver_info, self.ironic)
