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
from ironic_inspector.plugins import raid_device
from ironic_inspector.test import base as test_base


class TestRaidDeviceDetection(test_base.NodeTest):
    hook = raid_device.RaidDeviceDetection()

    def test_loadable_by_name(self):
        base.CONF.set_override('processing_hooks', 'raid_device', 'processing')
        ext = base.processing_hooks_manager()['raid_device']
        self.assertIsInstance(ext.obj, raid_device.RaidDeviceDetection)

    def test_missing_local_gb(self):
        introspection_data = {}
        self.hook.before_processing(introspection_data)

        self.assertEqual(1, introspection_data['local_gb'])

    def test_local_gb_not_changed(self):
        introspection_data = {'local_gb': 42}
        self.hook.before_processing(introspection_data)

        self.assertEqual(42, introspection_data['local_gb'])


class TestRaidDeviceDetectionUpdate(test_base.NodeTest):
    hook = raid_device.RaidDeviceDetection()

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def _check(self, data, patch, mock_patch):
        self.hook.before_processing(data)
        self.hook.before_update(data, self.node_info)
        self.assertCalledWithPatch(patch, mock_patch)

    def test_no_previous_block_devices(self):
        introspection_data = {'inventory': {
            'disks': [
                {'name': '/dev/sda', 'serial': 'foo'},
                {'name': '/dev/sdb', 'serial': 'bar'},
            ]
        }}
        expected = [{'op': 'add', 'path': '/extra/block_devices',
                     'value': {'serials': ['foo', 'bar']}}]
        self._check(introspection_data, expected)

    def test_no_previous_block_devices_old_ramdisk(self):
        introspection_data = {'block_devices': {'serials': ['foo', 'bar']}}
        expected = [{'op': 'add', 'path': '/extra/block_devices',
                     'value': introspection_data['block_devices']}]
        self._check(introspection_data, expected)

    def test_root_device_found(self):
        self.node.extra['block_devices'] = {'serials': ['foo', 'bar']}
        introspection_data = {'inventory': {
            'disks': [
                {'name': '/dev/sda', 'serial': 'foo'},
                {'name': '/dev/sdb', 'serial': 'baz'},
            ]
        }}
        expected = [{'op': 'remove', 'path': '/extra/block_devices'},
                    {'op': 'add', 'path': '/properties/root_device',
                     'value': {'serial': 'baz'}}]

        self._check(introspection_data, expected)

    def test_root_device_found_old_ramdisk(self):
        self.node.extra['block_devices'] = {'serials': ['foo', 'bar']}
        introspection_data = {'block_devices': {'serials': ['foo', 'baz']}}
        expected = [{'op': 'remove', 'path': '/extra/block_devices'},
                    {'op': 'add', 'path': '/properties/root_device',
                     'value': {'serial': 'baz'}}]

        self._check(introspection_data, expected)

    def test_root_device_already_exposed(self):
        self.node.properties['root_device'] = {'serial': 'foo'}
        introspection_data = {'inventory': {
            'disks': [
                {'name': '/dev/sda', 'serial': 'foo'},
                {'name': '/dev/sdb', 'serial': 'baz'},
            ]
        }}

        self._check(introspection_data, [])

    def test_multiple_new_devices(self):
        self.node.extra['block_devices'] = {'serials': ['foo', 'bar']}
        introspection_data = {'inventory': {
            'disks': [
                {'name': '/dev/sda', 'serial': 'foo'},
                {'name': '/dev/sdb', 'serial': 'baz'},
                {'name': '/dev/sdc', 'serial': 'qux'},
            ]
        }}

        self._check(introspection_data, [])

    def test_no_new_devices(self):
        self.node.extra['block_devices'] = {'serials': ['foo', 'bar']}
        introspection_data = {'inventory': {
            'disks': [
                {'name': '/dev/sda', 'serial': 'foo'},
                {'name': '/dev/sdb', 'serial': 'bar'},
            ]
        }}

        self._check(introspection_data, [])

    def test_no_block_devices_from_ramdisk(self):
        introspection_data = {}

        self._check(introspection_data, [])
