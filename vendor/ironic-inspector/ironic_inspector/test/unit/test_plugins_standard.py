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
from oslo_utils import units
import six

from ironic_inspector import node_cache
from ironic_inspector.plugins import base
from ironic_inspector.plugins import standard as std_plugins
from ironic_inspector import process
from ironic_inspector.test import base as test_base
from ironic_inspector import utils

CONF = cfg.CONF


@mock.patch('ironic_inspector.common.ironic.get_client', new=mock.Mock())
class TestSchedulerHook(test_base.NodeTest):
    def setUp(self):
        super(TestSchedulerHook, self).setUp()
        self.hook = std_plugins.SchedulerHook()
        self.node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                             node=self.node)

    def test_hook_loadable_by_name(self):
        CONF.set_override('processing_hooks', 'scheduler', 'processing')
        ext = base.processing_hooks_manager()['scheduler']
        self.assertIsInstance(ext.obj, std_plugins.SchedulerHook)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_ok(self, mock_patch):
        patch = [
            {'path': '/properties/cpus', 'value': '4', 'op': 'add'},
            {'path': '/properties/cpu_arch', 'value': 'x86_64', 'op': 'add'},
            {'path': '/properties/memory_mb', 'value': '12288', 'op': 'add'},
        ]

        self.hook.before_update(self.data, self.node_info)
        self.assertCalledWithPatch(patch, mock_patch)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_no_overwrite(self, mock_patch):
        CONF.set_override('overwrite_existing', False, 'processing')
        self.node.properties = {
            'memory_mb': '4096',
            'cpu_arch': 'i686'
        }
        patch = [
            {'path': '/properties/cpus', 'value': '4', 'op': 'add'},
        ]

        self.hook.before_update(self.data, self.node_info)
        self.assertCalledWithPatch(patch, mock_patch)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_missing_cpu(self, mock_patch):
        self.data['inventory']['cpu'] = {'count': 'none'}
        patch = [
            {'path': '/properties/memory_mb', 'value': '12288', 'op': 'add'},
        ]

        self.hook.before_update(self.data, self.node_info)
        self.assertCalledWithPatch(patch, mock_patch)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_missing_memory(self, mock_patch):
        # We require physical_mb, not total
        self.data['inventory']['memory'] = {'total': 42}
        patch = [
            {'path': '/properties/cpus', 'value': '4', 'op': 'add'},
            {'path': '/properties/cpu_arch', 'value': 'x86_64', 'op': 'add'},
        ]

        self.hook.before_update(self.data, self.node_info)
        self.assertCalledWithPatch(patch, mock_patch)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_no_data(self, mock_patch):
        self.data['inventory']['cpu'] = {}
        self.data['inventory']['memory'] = {}
        self.hook.before_update(self.data, self.node_info)

        del self.data['inventory']['cpu']
        del self.data['inventory']['memory']
        self.hook.before_update(self.data, self.node_info)

        self.assertFalse(mock_patch.called)


class TestValidateInterfacesHookLoad(test_base.NodeTest):
    def test_hook_loadable_by_name(self):
        CONF.set_override('processing_hooks', 'validate_interfaces',
                          'processing')
        ext = base.processing_hooks_manager()['validate_interfaces']
        self.assertIsInstance(ext.obj, std_plugins.ValidateInterfacesHook)


class TestValidateInterfacesHookBeforeProcessing(test_base.NodeTest):
    def setUp(self):
        super(TestValidateInterfacesHookBeforeProcessing, self).setUp()
        self.hook = std_plugins.ValidateInterfacesHook()

    def test_no_interfaces(self):
        self.assertRaisesRegex(utils.Error,
                               'Hardware inventory is empty or missing',
                               self.hook.before_processing, {})
        self.assertRaisesRegex(utils.Error,
                               'Hardware inventory is empty or missing',
                               self.hook.before_processing, {'inventory': {}})
        del self.inventory['interfaces']
        self.assertRaisesRegex(utils.Error,
                               'No network interfaces',
                               self.hook.before_processing, self.data)

    def test_only_pxe(self):
        self.hook.before_processing(self.data)

        self.assertEqual(self.pxe_interfaces, self.data['interfaces'])
        self.assertEqual([self.pxe_mac], self.data['macs'])
        self.assertEqual(self.all_interfaces, self.data['all_interfaces'])

    def test_only_pxe_mac_format(self):
        self.data['boot_interface'] = self.pxe_mac
        self.hook.before_processing(self.data)

        self.assertEqual(self.pxe_interfaces, self.data['interfaces'])
        self.assertEqual([self.pxe_mac], self.data['macs'])
        self.assertEqual(self.all_interfaces, self.data['all_interfaces'])

    def test_only_pxe_not_found(self):
        self.data['boot_interface'] = 'aa:bb:cc:dd:ee:ff'
        self.assertRaisesRegex(utils.Error, 'No suitable interfaces',
                               self.hook.before_processing, self.data)

    def test_only_pxe_no_boot_interface(self):
        del self.data['boot_interface']
        self.hook.before_processing(self.data)
        self.active_interfaces[self.pxe_iface_name]['pxe'] = False
        self.all_interfaces[self.pxe_iface_name]['pxe'] = False

        self.assertEqual(self.active_interfaces, self.data['interfaces'])
        self.assertEqual(sorted(i['mac'] for i in
                                self.active_interfaces.values()),
                         sorted(self.data['macs']))
        self.assertEqual(self.all_interfaces, self.data['all_interfaces'])

    def test_only_active(self):
        CONF.set_override('add_ports', 'active', 'processing')
        self.hook.before_processing(self.data)

        self.assertEqual(self.active_interfaces, self.data['interfaces'])
        self.assertEqual(sorted(i['mac'] for i in
                                self.active_interfaces.values()),
                         sorted(self.data['macs']))
        self.assertEqual(self.all_interfaces, self.data['all_interfaces'])

    def test_all(self):
        CONF.set_override('add_ports', 'all', 'processing')
        self.hook.before_processing(self.data)

        self.assertEqual(self.all_interfaces, self.data['interfaces'])
        self.assertEqual(sorted(i['mac'] for i in
                                self.all_interfaces.values()),
                         sorted(self.data['macs']))
        self.assertEqual(self.all_interfaces, self.data['all_interfaces'])

    @mock.patch.object(node_cache.NodeInfo, 'create_ports')
    def test_disabled_bad_conf(self, mock_create_port):
        CONF.set_override('add_ports', 'disabled', 'processing')
        CONF.set_override('keep_ports', 'added', 'processing')

        self.assertRaisesRegex(utils.Error, 'Configuration error:',
                               self.hook.__init__)
        mock_create_port.assert_not_called()

    @mock.patch.object(node_cache.NodeInfo, 'create_ports')
    def test_disabled(self, mock_create_port):
        CONF.set_override('add_ports', 'disabled', 'processing')
        CONF.set_override('keep_ports', 'all', 'processing')

        self.hook.before_processing(self.data)
        self.assertEqual(self.active_interfaces, self.data['interfaces'])
        mock_create_port.assert_not_called()

    def test_malformed_interfaces(self):
        self.inventory['interfaces'] = [
            # no name
            {'mac_address': '11:11:11:11:11:11', 'ipv4_address': '1.1.1.1'},
            # empty
            {},
        ]
        self.assertRaisesRegex(utils.Error, 'No interfaces supplied',
                               self.hook.before_processing, self.data)

    def test_skipped_interfaces(self):
        CONF.set_override('add_ports', 'all', 'processing')
        self.inventory['interfaces'] = [
            # local interface (by name)
            {'name': 'lo', 'mac_address': '11:11:11:11:11:11',
             'ipv4_address': '1.1.1.1'},
            # local interface (by IP address)
            {'name': 'em1', 'mac_address': '22:22:22:22:22:22',
             'ipv4_address': '127.0.0.1'},
            # no MAC provided
            {'name': 'em3', 'ipv4_address': '2.2.2.2'},
            # malformed MAC provided
            {'name': 'em4', 'mac_address': 'foobar',
             'ipv4_address': '2.2.2.2'},
        ]
        self.assertRaisesRegex(utils.Error, 'No suitable interfaces found',
                               self.hook.before_processing, self.data)

    def test_skipped_interfaces_with_local_address(self):
        CONF.set_override('add_ports', 'active', 'processing')
        self.inventory['interfaces'] = [
            # local interface (by IPv4 address)
            {'name': 'em1', 'mac_address': '22:22:22:22:22:22',
             'ipv4_address': '127.0.0.1'},
            # local interface (by IPv6 address)
            {'name': 'em2', 'mac_address': '33:33:33:33:33:33',
             'ipv6_address': '::1'},
            # interface only with local-link address
            {'name': 'em3', 'mac_address': '44:44:44:44:44:44',
             'ipv6_address': 'fe80::4644:44ff:fe44:4444'},
            # interface only with local-link address with suffix
            {'name': 'em4', 'mac_address': '55:55:55:55:55:55',
             'ipv6_address': 'fe80::5755:55ff:fe55:5555%em4'},
        ]
        self.assertRaisesRegex(utils.Error, 'No suitable interfaces found',
                               self.hook.before_processing, self.data)

    def test_interfaces_with_ipv6_addresses_only(self):
        CONF.set_override('add_ports', 'all', 'processing')
        self.inventory['interfaces'] = [
            # loopback interface (by IPv6 address)
            {'name': 'em2', 'mac_address': '33:33:33:33:33:33',
             'ipv6_address': '::1'},
            # interface with local-link address
            {'name': 'em3', 'mac_address': '44:44:44:44:44:44',
             'ipv6_address': 'fe80::4644:44ff:fe44:4444'},
            # interface with local-link address with suffix
            {'name': 'em4', 'mac_address': '55:55:55:55:55:55',
             'ipv6_address': 'fe80::5755:55ff:fe55:5555%em4'},
            # interface with ULA address
            {'name': 'em5', 'mac_address': '66:66:66:66:66:66',
             'ipv6_address': 'fd00::1111:2222:6666'},
        ]
        self.hook.before_processing(self.data)
        interfaces = self.data['interfaces']
        self.assertEqual(interfaces['em3']['mac'], '44:44:44:44:44:44')
        self.assertEqual(interfaces['em3']['ip'], 'fe80::4644:44ff:fe44:4444')
        self.assertEqual(interfaces['em4']['mac'], '55:55:55:55:55:55')
        self.assertEqual(interfaces['em4']['ip'], 'fe80::5755:55ff:fe55:5555')
        self.assertEqual(interfaces['em5']['mac'], '66:66:66:66:66:66')
        self.assertEqual(interfaces['em5']['ip'], 'fd00::1111:2222:6666')


@mock.patch.object(node_cache.NodeInfo, 'delete_port', autospec=True)
@mock.patch.object(node_cache.NodeInfo, 'create_ports', autospec=True)
class TestValidateInterfacesHookBeforeUpdateDeletion(test_base.NodeTest):
    def setUp(self):
        super(TestValidateInterfacesHookBeforeUpdateDeletion, self).setUp()
        self.hook = std_plugins.ValidateInterfacesHook()
        self.interfaces_to_create = sorted(self.valid_interfaces.values(),
                                           key=lambda i: i['mac'])
        self.existing_ports = [mock.Mock(spec=['address', 'uuid'],
                                         address=a)
                               for a in (self.macs[1],
                                         '44:44:44:44:44:44')]
        self.node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                             node=self.node,
                                             ports=self.existing_ports)

    def test_keep_all(self, mock_create_ports, mock_delete_port):
        self.hook.before_update(self.data, self.node_info)

        # NOTE(dtantsur): dictionary ordering is not defined
        mock_create_ports.assert_called_once_with(self.node_info, mock.ANY)
        self.assertEqual(self.interfaces_to_create,
                         sorted(mock_create_ports.call_args[0][1],
                                key=lambda i: i['mac']))

        self.assertFalse(mock_delete_port.called)

    def test_keep_present(self, mock_create_ports, mock_delete_port):
        CONF.set_override('keep_ports', 'present', 'processing')
        self.data['all_interfaces'] = self.all_interfaces
        self.hook.before_update(self.data, self.node_info)

        mock_create_ports.assert_called_once_with(self.node_info, mock.ANY)
        self.assertEqual(self.interfaces_to_create,
                         sorted(mock_create_ports.call_args[0][1],
                                key=lambda i: i['mac']))

        mock_delete_port.assert_called_once_with(self.node_info,
                                                 self.existing_ports[1])

    def test_keep_added(self, mock_create_ports, mock_delete_port):
        CONF.set_override('keep_ports', 'added', 'processing')
        self.data['macs'] = [self.pxe_mac]
        self.hook.before_update(self.data, self.node_info)

        mock_create_ports.assert_called_once_with(self.node_info, mock.ANY)
        self.assertEqual(self.interfaces_to_create,
                         sorted(mock_create_ports.call_args[0][1],
                                key=lambda i: i['mac']))

        mock_delete_port.assert_any_call(self.node_info,
                                         self.existing_ports[0])
        mock_delete_port.assert_any_call(self.node_info,
                                         self.existing_ports[1])


@mock.patch.object(node_cache.NodeInfo, 'patch_port', autospec=True)
@mock.patch.object(node_cache.NodeInfo, 'create_ports', autospec=True)
class TestValidateInterfacesHookBeforeUpdatePXEEnabled(test_base.NodeTest):
    def setUp(self):
        super(TestValidateInterfacesHookBeforeUpdatePXEEnabled, self).setUp()
        self.hook = std_plugins.ValidateInterfacesHook()
        # Note(milan) assumes the ordering of self.macs from test_base.NodeTest
        # where the first item '11:22:33:44:55:66' is the MAC of the
        # self.pxe_iface_name 'eth1', the "real" PXE interface
        sorted_interfaces = sorted(self.valid_interfaces.values(),
                                   key=lambda i: i['mac'])
        self.existing_ports = [
            mock.Mock(spec=['address', 'uuid', 'pxe_enabled'],
                      address=iface['mac'], pxe_enabled=True)
            for iface in sorted_interfaces
        ]
        self.node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                             node=self.node,
                                             ports=self.existing_ports)

    def test_fix_pxe_enabled(self, mock_create_ports, mock_patch_port):
        self.hook.before_update(self.data, self.node_info)
        # Note(milan) there are just 2 self.valid_interfaces, 'eth1' and 'ib0'
        # eth1 is the PXE booting interface and eth1.mac < ib0.mac
        mock_patch_port.assert_called_once_with(
            self.node_info, self.existing_ports[1],
            [{'op': 'replace', 'path': '/pxe_enabled', 'value': False}])

    def test_no_overwrite(self, mock_create_ports, mock_patch_port):
        CONF.set_override('overwrite_existing', False, 'processing')
        self.hook.before_update(self.data, self.node_info)
        self.assertFalse(mock_patch_port.called)


class TestRootDiskSelection(test_base.NodeTest):
    def setUp(self):
        super(TestRootDiskSelection, self).setUp()
        self.hook = std_plugins.RootDiskSelectionHook()
        self.inventory['disks'] = [
            {'model': 'Model 1', 'size': 20 * units.Gi, 'name': '/dev/sdb'},
            {'model': 'Model 2', 'size': 5 * units.Gi, 'name': '/dev/sda'},
            {'model': 'Model 3', 'size': 10 * units.Gi, 'name': '/dev/sdc'},
            {'model': 'Model 4', 'size': 4 * units.Gi, 'name': '/dev/sdd'},
            {'model': 'Too Small', 'size': 1 * units.Gi, 'name': '/dev/sde'},
        ]
        self.matched = self.inventory['disks'][2].copy()
        self.node_info = mock.Mock(spec=node_cache.NodeInfo,
                                   _state='foo',
                                   uuid=self.uuid,
                                   **{'node.return_value': self.node})

    def test_no_hints(self):
        del self.data['root_disk']

        self.hook.before_update(self.data, self.node_info)

        self.assertEqual(0, self.data['local_gb'])
        self.assertNotIn('root_disk', self.data)
        self.node_info.update_properties.assert_called_once_with(local_gb='0')

    def test_no_hints_no_overwrite(self):
        CONF.set_override('overwrite_existing', False, 'processing')
        del self.data['root_disk']

        self.hook.before_update(self.data, self.node_info)

        self.assertEqual(0, self.data['local_gb'])
        self.assertNotIn('root_disk', self.data)
        self.assertFalse(self.node_info.update_properties.called)

    def test_no_inventory(self):
        self.node.properties['root_device'] = {'model': 'foo'}
        del self.data['inventory']
        del self.data['root_disk']

        self.assertRaisesRegex(utils.Error,
                               'Hardware inventory is empty or missing',
                               self.hook.before_update,
                               self.data, self.node_info)

        self.assertNotIn('local_gb', self.data)
        self.assertNotIn('root_disk', self.data)
        self.assertFalse(self.node_info.update_properties.called)

    def test_no_disks(self):
        self.node.properties['root_device'] = {'size': 10}
        self.inventory['disks'] = []

        six.assertRaisesRegex(self, utils.Error,
                              'No disks satisfied root device hints',
                              self.hook.before_update,
                              self.data, self.node_info)

        self.assertNotIn('local_gb', self.data)
        self.assertFalse(self.node_info.update_properties.called)

    def test_one_matches(self):
        self.node.properties['root_device'] = {'size': 10}

        self.hook.before_update(self.data, self.node_info)

        self.assertEqual(self.matched, self.data['root_disk'])
        self.assertEqual(9, self.data['local_gb'])
        self.node_info.update_properties.assert_called_once_with(local_gb='9')

    def test_local_gb_without_spacing(self):
        CONF.set_override('disk_partitioning_spacing', False, 'processing')
        self.node.properties['root_device'] = {'size': 10}

        self.hook.before_update(self.data, self.node_info)

        self.assertEqual(self.matched, self.data['root_disk'])
        self.assertEqual(10, self.data['local_gb'])
        self.node_info.update_properties.assert_called_once_with(local_gb='10')

    def test_all_match(self):
        self.node.properties['root_device'] = {'size': 10,
                                               'model': 'Model 3'}

        self.hook.before_update(self.data, self.node_info)

        self.assertEqual(self.matched, self.data['root_disk'])
        self.assertEqual(9, self.data['local_gb'])
        self.node_info.update_properties.assert_called_once_with(local_gb='9')

    def test_one_fails(self):
        self.node.properties['root_device'] = {'size': 10,
                                               'model': 'Model 42'}
        del self.data['root_disk']

        self.assertRaisesRegex(utils.Error,
                               'No disks satisfied root device hints',
                               self.hook.before_update,
                               self.data, self.node_info)

        self.assertNotIn('local_gb', self.data)
        self.assertNotIn('root_disk', self.data)
        self.assertFalse(self.node_info.update_properties.called)

    def test_size_string(self):
        self.node.properties['root_device'] = {'size': '10'}
        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.matched, self.data['root_disk'])
        self.assertEqual(9, self.data['local_gb'])
        self.node_info.update_properties.assert_called_once_with(local_gb='9')

    def test_size_invalid(self):
        for bad_size in ('foo', None, {}):
            self.node.properties['root_device'] = {'size': bad_size}
            self.assertRaisesRegex(utils.Error,
                                   'No disks could be found',
                                   self.hook.before_update,
                                   self.data, self.node_info)

        self.assertNotIn('local_gb', self.data)
        self.assertFalse(self.node_info.update_properties.called)


class TestRamdiskError(test_base.InventoryTest):
    def setUp(self):
        super(TestRamdiskError, self).setUp()
        self.msg = 'BOOM'
        self.bmc_address = '1.2.3.4'
        self.data['error'] = self.msg

    def test_no_logs(self):
        self.assertRaisesRegex(utils.Error,
                               self.msg,
                               process.process, self.data)
