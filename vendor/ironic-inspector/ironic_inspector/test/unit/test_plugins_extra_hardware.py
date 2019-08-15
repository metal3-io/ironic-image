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

import json

import mock

from ironic_inspector import node_cache
from ironic_inspector.plugins import extra_hardware
from ironic_inspector.test import base as test_base
from ironic_inspector import utils


@mock.patch.object(extra_hardware.swift, 'SwiftAPI', autospec=True)
@mock.patch.object(node_cache.NodeInfo, 'patch')
class TestExtraHardware(test_base.NodeTest):
    hook = extra_hardware.ExtraHardwareHook()

    def test_data_recieved(self, patch_mock, swift_mock):
        introspection_data = {
            'data': [['memory', 'total', 'size', '4294967296'],
                     ['cpu', 'physical', 'number', '1'],
                     ['cpu', 'logical', 'number', '1']]}
        data = json.dumps(introspection_data['data'])
        self.hook.before_processing(introspection_data)
        self.hook.before_update(introspection_data, self.node_info)

        swift_conn = swift_mock.return_value
        name = 'extra_hardware-%s' % self.uuid
        swift_conn.create_object.assert_called_once_with(name, data)
        patch_mock.assert_called_once_with(
            [{'op': 'add', 'path': '/extra/hardware_swift_object',
              'value': name}])

        expected = {
            'memory': {
                'total': {
                    'size': 4294967296
                }
            },
            'cpu': {
                'physical': {
                    'number': 1
                },
                'logical': {
                    'number': 1
                },
            }
        }

        self.assertEqual(expected, introspection_data['extra'])

    def test_data_not_in_edeploy_format(self, patch_mock, swift_mock):
        introspection_data = {
            'data': [['memory', 'total', 'size', '4294967296'],
                     ['cpu', 'physical', 'number', '1'],
                     {'interface': 'eth1'}]}
        data = json.dumps(introspection_data['data'])
        self.hook.before_processing(introspection_data)
        self.hook.before_update(introspection_data, self.node_info)

        swift_conn = swift_mock.return_value
        name = 'extra_hardware-%s' % self.uuid
        swift_conn.create_object.assert_called_once_with(name, data)
        patch_mock.assert_called_once_with(
            [{'op': 'add', 'path': '/extra/hardware_swift_object',
              'value': name}])

        self.assertNotIn('data', introspection_data)

    def test_no_data_recieved(self, patch_mock, swift_mock):
        introspection_data = {'cats': 'meow'}
        swift_conn = swift_mock.return_value
        self.hook.before_processing(introspection_data)
        self.hook.before_update(introspection_data, self.node_info)
        self.assertFalse(patch_mock.called)
        self.assertFalse(swift_conn.create_object.called)

    def test__convert_edeploy_data(self, patch_mock, swift_mock):
        introspection_data = [['Sheldon', 'J.', 'Plankton', '123'],
                              ['Larry', 'the', 'Lobster', None],
                              ['Eugene', 'H.', 'Krabs', 'The cashier']]

        data = self.hook._convert_edeploy_data(introspection_data)
        expected_data = {'Sheldon': {'J.': {'Plankton': 123}},
                         'Larry': {'the': {'Lobster': None}},
                         'Eugene': {'H.': {'Krabs': 'The cashier'}}}
        self.assertEqual(expected_data, data)

    def test_swift_access_failed(self, patch_mock, swift_mock):
        introspection_data = {
            'data': [['memory', 'total', 'size', '4294967296'],
                     ['cpu', 'physical', 'number', '1'],
                     ['cpu', 'logical', 'number', '1']]}
        data = json.dumps(introspection_data['data'])
        name = 'extra_hardware-%s' % self.uuid

        swift_conn = swift_mock.return_value
        swift_conn.create_object.side_effect = utils.Error('no one')

        self.hook.before_processing(introspection_data)
        self.hook.before_update(introspection_data, self.node_info)

        swift_conn.create_object.assert_called_once_with(name, data)
        patch_mock.assert_not_called()

        expected = {
            'memory': {
                'total': {
                    'size': 4294967296
                }
            },
            'cpu': {
                'physical': {
                    'number': 1
                },
                'logical': {
                    'number': 1
                },
            }
        }

        self.assertNotIn('data', introspection_data)
        self.assertEqual(expected, introspection_data['extra'])
