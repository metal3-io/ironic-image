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

import datetime
import time

import fixtures
import futurist
import mock
from oslo_concurrency import lockutils
from oslo_config import fixture as config_fixture
from oslo_log import log
from oslo_utils import units
from oslo_utils import uuidutils
from oslotest import base as test_base

from ironic_inspector.common import i18n
import ironic_inspector.conf
from ironic_inspector.conf import opts as conf_opts
from ironic_inspector import db
from ironic_inspector import introspection_state as istate
from ironic_inspector import node_cache
from ironic_inspector.plugins import base as plugins_base
from ironic_inspector.test.unit import policy_fixture
from ironic_inspector import utils

CONF = ironic_inspector.conf.CONF


class BaseTest(test_base.BaseTestCase):

    IS_FUNCTIONAL = False

    def setUp(self):
        super(BaseTest, self).setUp()
        if not self.IS_FUNCTIONAL:
            self.init_test_conf()
        self.session = db.get_writer_session()
        engine = self.session.get_bind()
        db.Base.metadata.create_all(engine)
        engine.connect()
        self.addCleanup(engine.dispose)
        plugins_base.reset()
        node_cache._SEMAPHORES = lockutils.Semaphores()
        patch = mock.patch.object(i18n, '_', lambda s: s)
        patch.start()
        # 'p=patch' magic is due to how closures work
        self.addCleanup(lambda p=patch: p.stop())
        utils._EXECUTOR = futurist.SynchronousExecutor(green=True)

    def init_test_conf(self):
        CONF.reset()
        log.register_options(CONF)
        self.cfg = self.useFixture(config_fixture.Config(CONF))
        self.cfg.set_default('connection', "sqlite:///", group='database')
        self.cfg.set_default('slave_connection', None, group='database')
        self.cfg.set_default('max_retries', 10, group='database')
        conf_opts.parse_args([], default_config_files=[])
        self.policy = self.useFixture(policy_fixture.PolicyFixture())

    def assertPatchEqual(self, expected, actual):
        expected = sorted(expected, key=lambda p: p['path'])
        actual = sorted(actual, key=lambda p: p['path'])
        self.assertEqual(expected, actual)

    def assertCalledWithPatch(self, expected, mock_call):
        def _get_patch_param(call):
            try:
                if isinstance(call[0][1], list):
                    return call[0][1]
            except IndexError:
                pass
            return call[0][0]

        actual = sum(map(_get_patch_param, mock_call.call_args_list), [])
        self.assertPatchEqual(actual, expected)


class InventoryTest(BaseTest):
    def setUp(self):
        super(InventoryTest, self).setUp()
        # Prepare some realistic inventory
        # https://github.com/openstack/ironic-inspector/blob/master/HTTP-API.rst  # noqa
        self.bmc_address = '1.2.3.4'
        self.bmc_v6address = '2001:1234:1234:1234:1234:1234:1234:1234/64'
        self.macs = (
            ['11:22:33:44:55:66', '66:55:44:33:22:11', '7c:fe:90:29:26:52'])
        self.ips = ['1.2.1.2', '1.2.1.1', '1.2.1.3']
        self.inactive_mac = '12:12:21:12:21:12'
        self.pxe_mac = self.macs[0]
        self.all_macs = self.macs + [self.inactive_mac]
        self.pxe_iface_name = 'eth1'
        self.client_id = (
            'ff:00:00:00:00:00:02:00:00:02:c9:00:7c:fe:90:03:00:29:26:52')
        self.valid_interfaces = {
            self.pxe_iface_name: {'ip': self.ips[0], 'mac': self.macs[0],
                                  'client_id': None, 'pxe': True},
            'ib0': {'ip': self.ips[2], 'mac': self.macs[2],
                    'client_id': self.client_id, 'pxe': False}
        }
        self.data = {
            'boot_interface': '01-' + self.pxe_mac.replace(':', '-'),
            'inventory': {
                'interfaces': [
                    {'name': 'eth1', 'mac_address': self.macs[0],
                     'ipv4_address': self.ips[0],
                     'lldp': [
                         [1, "04112233aabbcc"],
                         [2, "07373334"],
                         [3, "003c"]]},
                    {'name': 'eth2', 'mac_address': self.inactive_mac},
                    {'name': 'eth3', 'mac_address': self.macs[1],
                     'ipv4_address': self.ips[1]},
                    {'name': 'ib0', 'mac_address': self.macs[2],
                     'ipv4_address': self.ips[2],
                     'client_id': self.client_id}
                ],
                'disks': [
                    {'name': '/dev/sda', 'model': 'Big Data Disk',
                     'size': 1000 * units.Gi},
                    {'name': '/dev/sdb', 'model': 'Small OS Disk',
                     'size': 20 * units.Gi},
                ],
                'cpu': {
                    'count': 4,
                    'architecture': 'x86_64'
                },
                'memory': {
                    'physical_mb': 12288
                },
                'bmc_address': self.bmc_address,
                'bmc_v6address': self.bmc_v6address
            },
            'root_disk': {'name': '/dev/sda', 'model': 'Big Data Disk',
                          'size': 1000 * units.Gi,
                          'wwn': None},
            'interfaces': self.valid_interfaces,
        }
        self.inventory = self.data['inventory']
        self.all_interfaces = {
            'eth1': {'mac': self.macs[0], 'ip': self.ips[0],
                     'client_id': None, 'pxe': True},
            'eth2': {'mac': self.inactive_mac, 'ip': None,
                     'client_id': None, 'pxe': False},
            'eth3': {'mac': self.macs[1], 'ip': self.ips[1],
                     'client_id': None, 'pxe': False},
            'ib0': {'mac': self.macs[2], 'ip': self.ips[2],
                    'client_id': self.client_id, 'pxe': False}
        }
        self.active_interfaces = {
            name: data
            for (name, data) in self.all_interfaces.items()
            if data.get('ip')
        }
        self.pxe_interfaces = {
            self.pxe_iface_name: self.all_interfaces[self.pxe_iface_name]
        }


class NodeTest(InventoryTest):
    def setUp(self):
        super(NodeTest, self).setUp()
        self.uuid = uuidutils.generate_uuid()
        fake_node = {
            'driver': 'ipmi',
            'driver_info': {'ipmi_address': self.bmc_address},
            'properties': {'cpu_arch': 'i386', 'local_gb': 40},
            'uuid': self.uuid,
            'power_state': 'power on',
            'provision_state': 'inspecting',
            'extra': {},
            'instance_uuid': None,
            'maintenance': False
        }
        mock_to_dict = mock.Mock(return_value=fake_node)

        self.node = mock.Mock(**fake_node)
        self.node.to_dict = mock_to_dict

        self.ports = []
        self.node_info = node_cache.NodeInfo(
            uuid=self.uuid,
            started_at=datetime.datetime(1, 1, 1),
            node=self.node, ports=self.ports)
        self.node_info.node = mock.Mock(return_value=self.node)
        self.sleep_fixture = self.useFixture(
            fixtures.MockPatchObject(time, 'sleep', autospec=True))


class NodeStateTest(NodeTest):
    def setUp(self):
        super(NodeStateTest, self).setUp()
        self.node_info._version_id = uuidutils.generate_uuid()
        self.node_info._state = istate.States.starting
        self.db_node = db.Node(uuid=self.node_info.uuid,
                               version_id=self.node_info._version_id,
                               state=self.node_info._state,
                               started_at=self.node_info.started_at,
                               finished_at=self.node_info.finished_at,
                               error=self.node_info.error)
        self.db_node.save(self.session)
