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

import socket
import unittest

from ironicclient import client
from ironicclient import exc as ironic_exc
import mock
from oslo_config import cfg

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector.common import keystone
from ironic_inspector.test import base
from ironic_inspector import utils


CONF = cfg.CONF


class TestGetClientBase(object):
    def test_get_client_with_auth_token(self, mock_client, mock_load,
                                        mock_opts, mock_adapter):
        fake_token = 'token'
        mock_sess = mock.Mock()
        mock_load.return_value = mock_sess
        ir_utils.get_client(fake_token)
        args = {'token': fake_token,
                'session': mock_sess,
                'os_ironic_api_version': ir_utils.DEFAULT_IRONIC_API_VERSION,
                'max_retries': CONF.ironic.max_retries,
                'retry_interval': CONF.ironic.retry_interval}
        endpoint = mock_adapter.return_value.get_endpoint.return_value
        mock_client.assert_called_once_with(1, endpoint=endpoint, **args)

    def test_get_client_without_auth_token(self, mock_client, mock_load,
                                           mock_opts, mock_adapter):
        mock_sess = mock.Mock()
        mock_load.return_value = mock_sess
        ir_utils.get_client(None)
        args = {'session': mock_sess,
                'os_ironic_api_version': ir_utils.DEFAULT_IRONIC_API_VERSION,
                'max_retries': CONF.ironic.max_retries,
                'retry_interval': CONF.ironic.retry_interval}
        endpoint = mock_adapter.return_value.get_endpoint.return_value
        mock_client.assert_called_once_with(1, endpoint=endpoint, **args)


@mock.patch.object(keystone, 'get_adapter')
@mock.patch.object(keystone, 'register_auth_opts')
@mock.patch.object(keystone, 'get_session')
@mock.patch.object(client, 'get_client', autospec=True)
class TestGetClientAuth(TestGetClientBase, base.BaseTest):
    def setUp(self):
        super(TestGetClientAuth, self).setUp()
        ir_utils.reset_ironic_session()
        self.cfg.config(auth_strategy='keystone')
        self.addCleanup(ir_utils.reset_ironic_session)


@mock.patch.object(keystone, 'get_adapter')
@mock.patch.object(keystone, 'register_auth_opts')
@mock.patch.object(keystone, 'get_session')
@mock.patch.object(client, 'get_client', autospec=True)
class TestGetClientNoAuth(TestGetClientBase, base.BaseTest):
    def setUp(self):
        super(TestGetClientNoAuth, self).setUp()
        ir_utils.reset_ironic_session()
        self.cfg.config(auth_strategy='noauth')
        self.addCleanup(ir_utils.reset_ironic_session)


class TestGetIpmiAddress(base.BaseTest):
    def setUp(self):
        super(TestGetIpmiAddress, self).setUp()
        self.ipmi_address = 'www.example.com'
        self.ipmi_ipv4 = '192.168.1.1'
        self.ipmi_ipv6 = 'fe80::1'

    def test_ipv4_in_resolves(self):
        node = mock.Mock(spec=['driver_info', 'uuid'],
                         driver_info={'ipmi_address': self.ipmi_ipv4})
        self.assertEqual((self.ipmi_ipv4, self.ipmi_ipv4, None),
                         ir_utils.get_ipmi_address(node))

    def test_ipv6_in_resolves(self):
        node = mock.Mock(spec=['driver_info', 'uuid'],
                         driver_info={'ipmi_address': self.ipmi_ipv6})
        self.assertEqual((self.ipmi_ipv6, None, self.ipmi_ipv6),
                         ir_utils.get_ipmi_address(node))

    @mock.patch('socket.getaddrinfo')
    def test_good_hostname_resolves(self, mock_socket):
        node = mock.Mock(spec=['driver_info', 'uuid'],
                         driver_info={'ipmi_address': self.ipmi_address})
        mock_socket.return_value = [
            (socket.AF_INET, None, None, None, (self.ipmi_ipv4,)),
            (socket.AF_INET6, None, None, None, (self.ipmi_ipv6,))]
        self.assertEqual((self.ipmi_address, self.ipmi_ipv4, self.ipmi_ipv6),
                         ir_utils.get_ipmi_address(node))
        mock_socket.assert_called_once_with(self.ipmi_address, None, 0, 0,
                                            socket.SOL_TCP)

    @mock.patch('socket.getaddrinfo')
    def test_bad_hostname_errors(self, mock_socket):
        node = mock.Mock(spec=['driver_info', 'uuid'],
                         driver_info={'ipmi_address': 'meow'},
                         uuid='uuid1')
        mock_socket.side_effect = socket.gaierror('Boom')
        self.assertRaises(utils.Error, ir_utils.get_ipmi_address, node)

    def test_additional_fields(self):
        node = mock.Mock(spec=['driver_info', 'uuid'],
                         driver_info={'foo': self.ipmi_ipv4})
        self.assertEqual((None, None, None),
                         ir_utils.get_ipmi_address(node))

        self.cfg.config(ipmi_address_fields=['foo', 'bar', 'baz'])
        self.assertEqual((self.ipmi_ipv4, self.ipmi_ipv4, None),
                         ir_utils.get_ipmi_address(node))

    def test_ipmi_bridging_enabled(self):
        node = mock.Mock(spec=['driver_info', 'uuid'],
                         driver_info={'ipmi_address': 'www.example.com',
                                      'ipmi_bridging': 'single'})
        self.assertEqual((None, None, None),
                         ir_utils.get_ipmi_address(node))

    def test_loopback_address(self):
        node = mock.Mock(spec=['driver_info', 'uuid'],
                         driver_info={'ipmi_address': '127.0.0.2'})
        self.assertEqual((None, None, None),
                         ir_utils.get_ipmi_address(node))


class TestCapabilities(unittest.TestCase):

    def test_capabilities_to_dict(self):
        capabilities = 'cat:meow,dog:wuff'
        expected_output = {'cat': 'meow', 'dog': 'wuff'}
        output = ir_utils.capabilities_to_dict(capabilities)
        self.assertEqual(expected_output, output)

    def test_dict_to_capabilities(self):
        capabilities_dict = {'cat': 'meow', 'dog': 'wuff'}
        output = ir_utils.dict_to_capabilities(capabilities_dict)
        self.assertIn('cat:meow', output)
        self.assertIn('dog:wuff', output)


class TestCallWithRetries(unittest.TestCase):
    def setUp(self):
        super(TestCallWithRetries, self).setUp()
        self.call = mock.Mock(spec=[])

    def test_no_retries_on_success(self):
        result = ir_utils.call_with_retries(self.call, 'meow', answer=42)
        self.assertEqual(result, self.call.return_value)
        self.call.assert_called_once_with('meow', answer=42)

    def test_no_retries_on_python_error(self):
        self.call.side_effect = RuntimeError('boom')
        self.assertRaisesRegexp(RuntimeError, 'boom',
                                ir_utils.call_with_retries,
                                self.call, 'meow', answer=42)
        self.call.assert_called_once_with('meow', answer=42)

    @mock.patch('time.sleep', lambda _x: None)
    def test_retries_on_ironicclient_error(self):
        self.call.side_effect = [
            ironic_exc.ClientException('boom')
        ] * 3 + [mock.sentinel.result]

        result = ir_utils.call_with_retries(self.call, 'meow', answer=42)
        self.assertEqual(result, mock.sentinel.result)
        self.call.assert_called_with('meow', answer=42)
        self.assertEqual(4, self.call.call_count)

    @mock.patch('time.sleep', lambda _x: None)
    def test_retries_on_ironicclient_error_with_failure(self):
        self.call.side_effect = ironic_exc.ClientException('boom')
        self.assertRaisesRegexp(ironic_exc.ClientException, 'boom',
                                ir_utils.call_with_retries,
                                self.call, 'meow', answer=42)
        self.call.assert_called_with('meow', answer=42)
        self.assertEqual(5, self.call.call_count)


class TestLookupNode(base.NodeTest):
    def setUp(self):
        super(TestLookupNode, self).setUp()
        self.ironic = mock.Mock(spec=['node', 'port'],
                                node=mock.Mock(spec=['list']),
                                port=mock.Mock(spec=['list']))
        self.ironic.node.list.return_value = [self.node]
        # Simulate only the PXE port enrolled
        self.port = mock.Mock(address=self.pxe_mac, node_uuid=self.node.uuid)
        self.ironic.port.list.side_effect = [
            [self.port]
        ] + [[]] * (len(self.macs) - 1)

    def test_no_input_no_result(self):
        self.assertIsNone(ir_utils.lookup_node())

    def test_lookup_by_mac_only(self):
        uuid = ir_utils.lookup_node(macs=self.macs, ironic=self.ironic)
        self.assertEqual(self.node.uuid, uuid)
        self.ironic.port.list.assert_has_calls([
            mock.call(address=mac) for mac in self.macs
        ])

    def test_lookup_by_mac_duplicates(self):
        self.ironic.port.list.side_effect = [
            [self.port],
            [mock.Mock(address=self.inactive_mac, node_uuid='another')]
        ] + [[]] * (len(self.macs) - 1)
        self.assertRaisesRegex(utils.Error, 'more than one node',
                               ir_utils.lookup_node,
                               macs=self.macs, ironic=self.ironic)
        self.ironic.port.list.assert_has_calls([
            mock.call(address=mac) for mac in self.macs
        ])

    def test_lookup_by_bmc_only(self):
        uuid = ir_utils.lookup_node(bmc_addresses=[self.bmc_address,
                                                   '42.42.42.42'],
                                    ironic=self.ironic)
        self.assertEqual(self.node.uuid, uuid)
        self.assertEqual(1, self.ironic.node.list.call_count)

    def test_lookup_by_bmc_duplicates(self):
        self.ironic.node.list.return_value = [
            self.node,
            mock.Mock(uuid='another',
                      driver_info={'ipmi_address': '42.42.42.42'}),
        ]
        self.assertRaisesRegex(utils.Error, 'more than one node',
                               ir_utils.lookup_node,
                               bmc_addresses=[self.bmc_address,
                                              '42.42.42.42'],
                               ironic=self.ironic)
        self.assertEqual(1, self.ironic.node.list.call_count)

    def test_lookup_by_both(self):
        uuid = ir_utils.lookup_node(bmc_addresses=[self.bmc_address,
                                                   self.bmc_v6address],
                                    macs=self.macs,
                                    ironic=self.ironic)
        self.assertEqual(self.node.uuid, uuid)
        self.ironic.port.list.assert_has_calls([
            mock.call(address=mac) for mac in self.macs
        ])
        self.assertEqual(1, self.ironic.node.list.call_count)

    def test_lookup_by_both_duplicates(self):
        self.ironic.port.list.side_effect = [
            [mock.Mock(address=self.inactive_mac, node_uuid='another')]
        ] + [[]] * (len(self.macs) - 1)
        self.assertRaisesRegex(utils.Error, 'correspond to different nodes',
                               ir_utils.lookup_node,
                               bmc_addresses=[self.bmc_address,
                                              self.bmc_v6address],
                               macs=self.macs,
                               ironic=self.ironic)
        self.ironic.port.list.assert_has_calls([
            mock.call(address=mac) for mac in self.macs
        ])
        self.assertEqual(1, self.ironic.node.list.call_count)
