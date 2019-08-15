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

import socket

import mock
from oslo_config import cfg
import zeroconf

from ironic_lib import exception
from ironic_lib import mdns
from ironic_lib.tests import base

CONF = cfg.CONF


@mock.patch.object(zeroconf, 'Zeroconf', autospec=True)
class RegisterServiceTestCase(base.IronicLibTestCase):

    def test_ok(self, mock_zc):
        zc = mdns.Zeroconf()
        zc.register_service('baremetal', 'https://127.0.0.1/baremetal')
        mock_zc.assert_called_once_with(
            interfaces=zeroconf.InterfaceChoice.All)
        mock_zc.return_value.register_service.assert_called_once_with(mock.ANY)
        info = mock_zc.return_value.register_service.call_args[0][0]
        self.assertEqual('_openstack._tcp.local.', info.type)
        self.assertEqual('baremetal._openstack._tcp.local.', info.name)
        self.assertEqual('127.0.0.1', socket.inet_ntoa(info.address))
        self.assertEqual({'path': '/baremetal'}, info.properties)

    def test_with_params(self, mock_zc):
        CONF.set_override('params', {'answer': 'none', 'foo': 'bar'},
                          group='mdns')
        zc = mdns.Zeroconf()
        zc.register_service('baremetal', 'https://127.0.0.1/baremetal',
                            params={'answer': 42})
        mock_zc.return_value.register_service.assert_called_once_with(mock.ANY)
        info = mock_zc.return_value.register_service.call_args[0][0]
        self.assertEqual('_openstack._tcp.local.', info.type)
        self.assertEqual('baremetal._openstack._tcp.local.', info.name)
        self.assertEqual('127.0.0.1', socket.inet_ntoa(info.address))
        self.assertEqual({'path': '/baremetal',
                          'answer': 42,
                          'foo': 'bar'},
                         info.properties)

    @mock.patch.object(mdns.time, 'sleep', autospec=True)
    def test_with_race(self, mock_sleep, mock_zc):
        mock_zc.return_value.register_service.side_effect = [
            zeroconf.NonUniqueNameException,
            zeroconf.NonUniqueNameException,
            zeroconf.NonUniqueNameException,
            None
        ]
        zc = mdns.Zeroconf()
        zc.register_service('baremetal', 'https://127.0.0.1/baremetal')
        mock_zc.return_value.register_service.assert_called_with(mock.ANY)
        self.assertEqual(4, mock_zc.return_value.register_service.call_count)
        mock_sleep.assert_has_calls([mock.call(i) for i in (0.1, 0.2, 0.4)])

    def test_with_interfaces(self, mock_zc):
        CONF.set_override('interfaces', ['10.0.0.1', '192.168.1.1'],
                          group='mdns')
        zc = mdns.Zeroconf()
        zc.register_service('baremetal', 'https://127.0.0.1/baremetal')
        mock_zc.assert_called_once_with(interfaces=['10.0.0.1', '192.168.1.1'])
        mock_zc.return_value.register_service.assert_called_once_with(mock.ANY)
        info = mock_zc.return_value.register_service.call_args[0][0]
        self.assertEqual('_openstack._tcp.local.', info.type)
        self.assertEqual('baremetal._openstack._tcp.local.', info.name)
        self.assertEqual('127.0.0.1', socket.inet_ntoa(info.address))
        self.assertEqual({'path': '/baremetal'}, info.properties)

    @mock.patch.object(mdns.time, 'sleep', autospec=True)
    def test_failure(self, mock_sleep, mock_zc):
        mock_zc.return_value.register_service.side_effect = (
            zeroconf.NonUniqueNameException
        )
        zc = mdns.Zeroconf()
        self.assertRaises(exception.ServiceRegistrationFailure,
                          zc.register_service,
                          'baremetal', 'https://127.0.0.1/baremetal')
        mock_zc.return_value.register_service.assert_called_with(mock.ANY)
        self.assertEqual(CONF.mdns.registration_attempts,
                         mock_zc.return_value.register_service.call_count)
        self.assertEqual(CONF.mdns.registration_attempts - 1,
                         mock_sleep.call_count)


class ParseEndpointTestCase(base.IronicLibTestCase):

    def test_simple(self):
        endpoint = mdns._parse_endpoint('http://127.0.0.1')
        self.assertEqual('127.0.0.1', socket.inet_ntoa(endpoint.ip))
        self.assertEqual(80, endpoint.port)
        self.assertEqual({}, endpoint.params)
        self.assertIsNone(endpoint.hostname)

    def test_simple_https(self):
        endpoint = mdns._parse_endpoint('https://127.0.0.1')
        self.assertEqual('127.0.0.1', socket.inet_ntoa(endpoint.ip))
        self.assertEqual(443, endpoint.port)
        self.assertEqual({}, endpoint.params)
        self.assertIsNone(endpoint.hostname)

    def test_with_path_and_port(self):
        endpoint = mdns._parse_endpoint('http://127.0.0.1:8080/bm')
        self.assertEqual('127.0.0.1', socket.inet_ntoa(endpoint.ip))
        self.assertEqual(8080, endpoint.port)
        self.assertEqual({'path': '/bm', 'protocol': 'http'}, endpoint.params)
        self.assertIsNone(endpoint.hostname)

    @mock.patch.object(socket, 'gethostbyname', autospec=True)
    def test_resolve(self, mock_resolve):
        mock_resolve.return_value = '1.2.3.4'
        endpoint = mdns._parse_endpoint('http://example.com')
        self.assertEqual('1.2.3.4', socket.inet_ntoa(endpoint.ip))
        self.assertEqual(80, endpoint.port)
        self.assertEqual({}, endpoint.params)
        self.assertEqual('example.com.', endpoint.hostname)
        mock_resolve.assert_called_once_with('example.com')


@mock.patch('zeroconf.Zeroconf', autospec=True)
class GetEndpointTestCase(base.IronicLibTestCase):
    def test_simple(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=80,
            properties={}
        )

        endp, params = mdns.get_endpoint('baremetal')
        self.assertEqual('http://192.168.1.1:80', endp)
        self.assertEqual({}, params)
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )
        mock_zc.return_value.close.assert_called_once_with()

    def test_https(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=443,
            properties={}
        )

        endp, params = mdns.get_endpoint('baremetal')
        self.assertEqual('https://192.168.1.1:443', endp)
        self.assertEqual({}, params)
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )

    def test_with_custom_port_and_path(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=8080,
            properties={b'path': b'/baremetal'}
        )

        endp, params = mdns.get_endpoint('baremetal')
        self.assertEqual('https://192.168.1.1:8080/baremetal', endp)
        self.assertEqual({}, params)
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )

    def test_with_custom_port_path_and_protocol(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=8080,
            properties={b'path': b'/baremetal', b'protocol': b'http'}
        )

        endp, params = mdns.get_endpoint('baremetal')
        self.assertEqual('http://192.168.1.1:8080/baremetal', endp)
        self.assertEqual({}, params)
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )

    def test_with_params(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=80,
            properties={b'ipa_debug': True}
        )

        endp, params = mdns.get_endpoint('baremetal')
        self.assertEqual('http://192.168.1.1:80', endp)
        self.assertEqual({'ipa_debug': True}, params)
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )

    def test_binary_data(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=80,
            properties={b'ipa_debug': True, b'binary': b'\xe2\x28\xa1'}
        )

        endp, params = mdns.get_endpoint('baremetal')
        self.assertEqual('http://192.168.1.1:80', endp)
        self.assertEqual({'ipa_debug': True, 'binary': b'\xe2\x28\xa1'},
                         params)
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )

    def test_invalid_key(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=80,
            properties={b'ipa_debug': True, b'\xc3\x28': b'value'}
        )

        self.assertRaisesRegex(exception.ServiceLookupFailure,
                               'Cannot decode key',
                               mdns.get_endpoint, 'baremetal')
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )

    def test_with_server(self, mock_zc):
        mock_zc.return_value.get_service_info.return_value = mock.Mock(
            address=socket.inet_aton('192.168.1.1'),
            port=443,
            server='openstack.example.com.',
            properties={}
        )

        endp, params = mdns.get_endpoint('baremetal')
        self.assertEqual('https://openstack.example.com:443', endp)
        self.assertEqual({}, params)
        mock_zc.return_value.get_service_info.assert_called_once_with(
            'baremetal._openstack._tcp.local.',
            'baremetal._openstack._tcp.local.'
        )

    @mock.patch('time.sleep', autospec=True)
    def test_not_found(self, mock_sleep, mock_zc):
        mock_zc.return_value.get_service_info.return_value = None

        self.assertRaisesRegex(exception.ServiceLookupFailure,
                               'baremetal service',
                               mdns.get_endpoint, 'baremetal')
        self.assertEqual(CONF.mdns.lookup_attempts - 1, mock_sleep.call_count)
