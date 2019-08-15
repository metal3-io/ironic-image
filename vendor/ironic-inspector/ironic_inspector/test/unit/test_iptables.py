# Copyright 2015 NEC Corporation
# All Rights Reserved.
#
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

import fixtures
from ironicclient import exc as ironic_exc
import mock
from oslo_config import cfg

from ironic_inspector import node_cache
from ironic_inspector.pxe_filter import base as pxe_filter
from ironic_inspector.pxe_filter import iptables
from ironic_inspector.test import base as test_base


CONF = cfg.CONF


class TestIptablesDriver(test_base.NodeTest):

    def setUp(self):
        super(TestIptablesDriver, self).setUp()
        CONF.set_override('rootwrap_config', '/some/fake/path')
        # NOTE(milan) we ignore the state checking in order to avoid having to
        # always call e.g self.driver.init_filter() to set proper driver state
        self.mock_fsm = self.useFixture(
            fixtures.MockPatchObject(iptables.IptablesFilter, 'fsm')).mock
        self.mock_call = self.useFixture(
            fixtures.MockPatchObject(iptables.processutils, 'execute')).mock
        self.driver = iptables.IptablesFilter()
        self.mock_iptables = self.useFixture(
            fixtures.MockPatchObject(self.driver, '_iptables')).mock
        self.mock_should_enable_dhcp = self.useFixture(
            fixtures.MockPatchObject(iptables, '_should_enable_dhcp')).mock
        self.mock__get_blacklist = self.useFixture(
            fixtures.MockPatchObject(iptables, '_get_blacklist')).mock
        self.mock__get_blacklist.return_value = []
        self.mock_ironic = mock.Mock()

    def check_fsm(self, events):
        # assert the iptables.fsm.process_event() was called with the events
        calls = [mock.call(event) for event in events]
        self.assertEqual(calls, self.driver.fsm.process_event.call_args_list)

    def test_init_args(self):
        self.driver.init_filter()
        init_expected_args = [
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport', '67',
             '-j', self.driver.chain),
            ('-F', self.driver.chain),
            ('-X', self.driver.chain),
            ('-N', self.driver.chain)]

        call_args_list = self.mock_iptables.call_args_list

        for (args, call) in zip(init_expected_args, call_args_list):
            self.assertEqual(args, call[0])

        expected = ('sudo', 'ironic-inspector-rootwrap', CONF.rootwrap_config,
                    'iptables', '-w')
        self.assertEqual(expected, self.driver.base_command)
        self.check_fsm([pxe_filter.Events.initialize])

    def test_init_args_old_iptables(self):
        exc = iptables.processutils.ProcessExecutionError(2, '')
        self.mock_call.side_effect = exc
        self.driver.init_filter()
        init_expected_args = [
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport', '67',
             '-j', self.driver.chain),
            ('-F', self.driver.chain),
            ('-X', self.driver.chain),
            ('-N', self.driver.chain)]

        call_args_list = self.mock_iptables.call_args_list

        for (args, call) in zip(init_expected_args, call_args_list):
            self.assertEqual(args, call[0])

        expected = ('sudo', 'ironic-inspector-rootwrap', CONF.rootwrap_config,
                    'iptables',)
        self.assertEqual(expected, self.driver.base_command)
        self.check_fsm([pxe_filter.Events.initialize])

    def test_init_kwargs(self):
        self.driver.init_filter()
        init_expected_kwargs = [
            {'ignore': True},
            {'ignore': True},
            {'ignore': True}]

        call_args_list = self.mock_iptables.call_args_list

        for (kwargs, call) in zip(init_expected_kwargs, call_args_list):
            self.assertEqual(kwargs, call[1])
        self.check_fsm([pxe_filter.Events.initialize])

    def test_init_fails(self):
        class MyError(Exception):
            pass

        self.mock_call.side_effect = MyError('Oops!')
        self.assertRaisesRegex(MyError, 'Oops!', self.driver.init_filter)
        self.check_fsm([pxe_filter.Events.initialize, pxe_filter.Events.reset])

    def _test__iptables_args(self, expected_port):
        self.driver = iptables.IptablesFilter()
        self.mock_iptables = self.useFixture(
            fixtures.MockPatchObject(self.driver, '_iptables')).mock
        self.mock_should_enable_dhcp.return_value = True

        _iptables_expected_args = [
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.new_chain),
            ('-F', self.driver.new_chain),
            ('-X', self.driver.new_chain),
            ('-N', self.driver.new_chain),
            ('-A', self.driver.new_chain, '-j', 'ACCEPT'),
            ('-I', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.new_chain),
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.chain),
            ('-F', self.driver.chain),
            ('-X', self.driver.chain),
            ('-E', self.driver.new_chain, self.driver.chain)
        ]

        self.driver.sync(self.mock_ironic)
        call_args_list = self.mock_iptables.call_args_list

        for (args, call) in zip(_iptables_expected_args,
                                call_args_list):
            self.assertEqual(args, call[0])
        self.mock__get_blacklist.assert_called_once_with(self.mock_ironic)
        self.check_fsm([pxe_filter.Events.sync])

    def test__iptables_args_ipv4(self):
        CONF.set_override('ip_version', '4', 'iptables')
        self._test__iptables_args('67')

    def test__iptables_args_ipv6(self):
        CONF.set_override('ip_version', '6', 'iptables')
        self._test__iptables_args('547')

    def test__iptables_kwargs(self):
        _iptables_expected_kwargs = [
            {'ignore': True},
            {'ignore': True},
            {'ignore': True},
            {},
            {},
            {},
            {'ignore': True},
            {'ignore': True},
            {'ignore': True}
        ]

        self.driver.sync(self.mock_ironic)
        call_args_list = self.mock_iptables.call_args_list

        for (kwargs, call) in zip(_iptables_expected_kwargs,
                                  call_args_list):
            self.assertEqual(kwargs, call[1])
        self.check_fsm([pxe_filter.Events.sync])

    def _test_sync_with_blacklist(self, expected_port):
        self.driver = iptables.IptablesFilter()
        self.mock_iptables = self.useFixture(
            fixtures.MockPatchObject(self.driver, '_iptables')).mock
        self.mock__get_blacklist.return_value = ['AA:BB:CC:DD:EE:FF']
        self.mock_should_enable_dhcp.return_value = True

        _iptables_expected_args = [
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.new_chain),
            ('-F', self.driver.new_chain),
            ('-X', self.driver.new_chain),
            ('-N', self.driver.new_chain),
            # Blacklist
            ('-A', self.driver.new_chain, '-m', 'mac', '--mac-source',
             self.mock__get_blacklist.return_value[0], '-j', 'DROP'),
            ('-A', self.driver.new_chain, '-j', 'ACCEPT'),
            ('-I', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.new_chain),
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.chain),
            ('-F', self.driver.chain),
            ('-X', self.driver.chain),
            ('-E', self.driver.new_chain, self.driver.chain)
        ]

        self.driver.sync(self.mock_ironic)
        self.check_fsm([pxe_filter.Events.sync])
        call_args_list = self.mock_iptables.call_args_list

        for (args, call) in zip(_iptables_expected_args,
                                call_args_list):
            self.assertEqual(args, call[0])
        self.mock__get_blacklist.assert_called_once_with(self.mock_ironic)

        # check caching

        self.mock_iptables.reset_mock()
        self.mock__get_blacklist.reset_mock()
        self.driver.sync(self.mock_ironic)
        self.mock__get_blacklist.assert_called_once_with(self.mock_ironic)
        self.assertFalse(self.mock_iptables.called)

    def test_sync_with_blacklist_ipv4(self):
        CONF.set_override('ip_version', '4', 'iptables')
        self._test_sync_with_blacklist('67')

    def test_sync_with_blacklist_ipv6(self):
        CONF.set_override('ip_version', '6', 'iptables')
        self._test_sync_with_blacklist('547')

    def _test__iptables_clean_cache_on_error(self, expected_port):
        self.driver = iptables.IptablesFilter()
        self.mock_iptables = self.useFixture(
            fixtures.MockPatchObject(self.driver, '_iptables')).mock
        self.mock__get_blacklist.return_value = ['AA:BB:CC:DD:EE:FF']
        self.mock_should_enable_dhcp.return_value = True

        self.mock_iptables.side_effect = [None, None, RuntimeError('Oops!'),
                                          None, None, None, None, None, None]
        self.assertRaises(RuntimeError, self.driver.sync, self.mock_ironic)
        self.check_fsm([pxe_filter.Events.sync, pxe_filter.Events.reset])
        self.mock__get_blacklist.assert_called_once_with(self.mock_ironic)

        # check caching
        syncs_expected_args = [
            # driver reset
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.new_chain),
            ('-F', self.driver.new_chain),
            ('-X', self.driver.new_chain),
            ('-N', self.driver.new_chain),
            # Blacklist
            ('-A', self.driver.new_chain, '-m', 'mac', '--mac-source',
             self.mock__get_blacklist.return_value[0], '-j', 'DROP'),
            ('-A', self.driver.new_chain, '-j', 'ACCEPT'),
            ('-I', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.new_chain),
            ('-D', 'INPUT', '-i', 'br-ctlplane', '-p', 'udp', '--dport',
             expected_port, '-j', self.driver.chain),
            ('-F', self.driver.chain),
            ('-X', self.driver.chain),
            ('-E', self.driver.new_chain, self.driver.chain)
        ]

        self.mock_iptables.reset_mock()
        self.mock_iptables.side_effect = None
        self.mock__get_blacklist.reset_mock()
        self.mock_fsm.reset_mock()
        self.driver.sync(self.mock_ironic)
        self.check_fsm([pxe_filter.Events.sync])
        call_args_list = self.mock_iptables.call_args_list

        for (idx, (args, call)) in enumerate(zip(syncs_expected_args,
                                                 call_args_list)):
            self.assertEqual(args, call[0], 'idx: %s' % idx)
        self.mock__get_blacklist.assert_called_once_with(self.mock_ironic)

    def test__iptables_clean_cache_on_error_ipv4(self):
        CONF.set_override('ip_version', '4', 'iptables')
        self._test__iptables_clean_cache_on_error('67')

    def test__iptables_clean_cache_on_error_ipv6(self):
        CONF.set_override('ip_version', '6', 'iptables')
        self._test__iptables_clean_cache_on_error('547')

    def test_iptables_command_ipv4(self):
        CONF.set_override('ip_version', '4', 'iptables')
        driver = iptables.IptablesFilter()
        self.assertEqual(driver._cmd_iptables, 'iptables')

    def test_iptables_command_ipv6(self):
        CONF.set_override('ip_version', '6', 'iptables')
        driver = iptables.IptablesFilter()
        self.assertEqual(driver._cmd_iptables, 'ip6tables')


class Test_ShouldEnableDhcp(test_base.BaseTest):
    def setUp(self):
        super(Test_ShouldEnableDhcp, self).setUp()
        self.mock_introspection_active = self.useFixture(
            fixtures.MockPatchObject(node_cache, 'introspection_active')).mock

    def test_introspection_active(self):
        self.mock_introspection_active.return_value = True
        self.assertIs(True, iptables._should_enable_dhcp())

    def test_node_not_found_hook_set(self):
        # DHCP should be always opened if node_not_found hook is set
        CONF.set_override('node_not_found_hook', 'enroll', 'processing')
        self.mock_introspection_active.return_value = False
        self.assertIs(True, iptables._should_enable_dhcp())

    def test__should_enable_dhcp_false(self):
        self.mock_introspection_active.return_value = False
        self.assertIs(False, iptables._should_enable_dhcp())


class TestIBMapping(test_base.BaseTest):
    def setUp(self):
        super(TestIBMapping, self).setUp()
        CONF.set_override('ethoib_interfaces', ['eth0'], 'iptables')
        self.ib_data = (
            'EMAC=02:00:02:97:00:01 IMAC=97:fe:80:00:00:00:00:00:00:7c:fe:90:'
            '03:00:29:26:52\n'
            'EMAC=02:00:00:61:00:02 IMAC=61:fe:80:00:00:00:00:00:00:7c:fe:90:'
            '03:00:29:24:4f\n'
        )
        self.client_id = ('ff:00:00:00:00:00:02:00:00:02:c9:00:7c:fe:90:03:00:'
                          '29:24:4f')
        self.ib_address = '7c:fe:90:29:24:4f'
        self.ib_port = mock.Mock(address=self.ib_address,
                                 extra={'client-id': self.client_id},
                                 spec=['address', 'extra'])
        self.port = mock.Mock(address='aa:bb:cc:dd:ee:ff',
                              extra={}, spec=['address', 'extra'])
        self.ports = [self.ib_port, self.port]
        self.expected_rmac = '02:00:00:61:00:02'
        self.fileobj = mock.mock_open(read_data=self.ib_data)

    def test_matching_ib(self):
        with mock.patch('six.moves.builtins.open', self.fileobj,
                        create=True) as mock_open:
            iptables._ib_mac_to_rmac_mapping(self.ports)

        self.assertEqual(self.expected_rmac, self.ib_port.address)
        self.assertEqual(self.ports, [self.ib_port, self.port])
        mock_open.assert_called_once_with('/sys/class/net/eth0/eth/neighs',
                                          'r')

    def test_ib_not_match(self):
        self.ports[0].extra['client-id'] = 'foo'
        with mock.patch('six.moves.builtins.open', self.fileobj,
                        create=True) as mock_open:
            iptables._ib_mac_to_rmac_mapping(self.ports)

        self.assertEqual(self.ib_address, self.ib_port.address)
        self.assertEqual(self.ports, [self.ib_port, self.port])
        mock_open.assert_called_once_with('/sys/class/net/eth0/eth/neighs',
                                          'r')

    def test_open_no_such_file(self):
        with mock.patch('six.moves.builtins.open',
                        side_effect=IOError()) as mock_open:
            iptables._ib_mac_to_rmac_mapping(self.ports)

        self.assertEqual(self.ib_address, self.ib_port.address)
        self.assertEqual(self.ports, [self.ib_port, self.port])
        mock_open.assert_called_once_with('/sys/class/net/eth0/eth/neighs',
                                          'r')

    def test_no_interfaces(self):
        CONF.set_override('ethoib_interfaces', [], 'iptables')
        with mock.patch('six.moves.builtins.open', self.fileobj,
                        create=True) as mock_open:
            iptables._ib_mac_to_rmac_mapping(self.ports)

        self.assertEqual(self.ib_address, self.ib_port.address)
        self.assertEqual(self.ports, [self.ib_port, self.port])
        mock_open.assert_not_called()


class TestGetBlacklist(test_base.BaseTest):
    def setUp(self):
        super(TestGetBlacklist, self).setUp()
        self.mock__ib_mac_to_rmac_mapping = self.useFixture(
            fixtures.MockPatchObject(iptables, '_ib_mac_to_rmac_mapping')).mock
        self.mock_active_macs = self.useFixture(
            fixtures.MockPatchObject(node_cache, 'active_macs')).mock
        self.mock_ironic = mock.Mock()

    def test_active_port(self):
        mock_ports_list = [
            mock.Mock(address='foo'),
            mock.Mock(address='bar'),
        ]
        self.mock_ironic.port.list.return_value = mock_ports_list
        self.mock_active_macs.return_value = {'foo'}

        ports = iptables._get_blacklist(self.mock_ironic)
        # foo is an active address so we expect the blacklist contains only bar
        self.assertEqual(['bar'], ports)
        self.mock_ironic.port.list.assert_called_once_with(
            limit=0, fields=['address', 'extra'])
        self.mock__ib_mac_to_rmac_mapping.assert_called_once_with(
            [mock_ports_list[1]])

    @mock.patch('time.sleep', lambda _x: None)
    def test_retry_on_port_list_failure(self):
        mock_ports_list = [
            mock.Mock(address='foo'),
            mock.Mock(address='bar'),
        ]
        self.mock_ironic.port.list.side_effect = [
            ironic_exc.ConnectionRefused('boom'),
            mock_ports_list
        ]
        self.mock_active_macs.return_value = {'foo'}

        ports = iptables._get_blacklist(self.mock_ironic)
        # foo is an active address so we expect the blacklist contains only bar
        self.assertEqual(['bar'], ports)
        self.mock_ironic.port.list.assert_called_with(
            limit=0, fields=['address', 'extra'])
        self.mock__ib_mac_to_rmac_mapping.assert_called_once_with(
            [mock_ports_list[1]])
