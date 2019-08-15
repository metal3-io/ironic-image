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

from ironicclient.v1 import node
from keystonemiddleware import auth_token
import mock
from oslo_config import cfg

from ironic_inspector.common import context
from ironic_inspector import node_cache
from ironic_inspector.test import base
from ironic_inspector import utils

CONF = cfg.CONF


class TestCheckAuth(base.BaseTest):
    def setUp(self):
        super(TestCheckAuth, self).setUp()
        self.cfg.config(auth_strategy='keystone')

    @mock.patch.object(auth_token, 'AuthProtocol')
    def test_middleware(self, mock_auth):
        self.cfg.config(group='keystone_authtoken',
                        admin_user='admin',
                        admin_tenant_name='admin',
                        admin_password='password',
                        www_authenticate_uri='http://127.0.0.1:5000',
                        identity_uri='http://127.0.0.1:35357')

        app = mock.Mock(wsgi_app=mock.sentinel.app)
        utils.add_auth_middleware(app)

        call_args = mock_auth.call_args_list[0]
        args = call_args[0]
        self.assertEqual(mock.sentinel.app, args[0])
        args1 = args[1]

        self.assertEqual('admin', args1['admin_user'])
        self.assertEqual('admin', args1['admin_tenant_name'])
        self.assertEqual('password', args1['admin_password'])
        self.assertTrue(args1['delay_auth_decision'])
        self.assertEqual('http://127.0.0.1:5000',
                         args1['www_authenticate_uri'])
        self.assertEqual('http://127.0.0.1:35357', args1['identity_uri'])

    def test_admin(self):
        request = mock.Mock(headers={'X-Identity-Status': 'Confirmed'})
        request.context = context.RequestContext(roles=['admin'])
        utils.check_auth(request, rule="is_admin")

    def test_invalid(self):
        request = mock.Mock(headers={'X-Identity-Status': 'Invalid'})
        request.context = context.RequestContext()
        self.assertRaises(utils.Error, utils.check_auth, request)

    def test_not_admin(self):
        request = mock.Mock(headers={'X-Identity-Status': 'Confirmed'})
        request.context = context.RequestContext(roles=['member'])
        self.assertRaises(utils.Error, utils.check_auth, request,
                          rule="is_admin")

    def test_disabled(self):
        self.cfg.config(auth_strategy='noauth')
        request = mock.Mock(headers={'X-Identity-Status': 'Invalid'})
        utils.check_auth(request)

    def test_public_api(self):
        request = mock.Mock(headers={'X-Identity-Status': 'Invalid'})
        request.context = context.RequestContext(is_public_api=True)
        utils.check_auth(request, "public_api")


class TestProcessingLogger(base.BaseTest):
    def test_prefix_no_info(self):
        self.assertEqual('[unidentified node]',
                         utils.processing_logger_prefix())

    def test_prefix_only_uuid(self):
        node_info = node.Node(mock.Mock(), dict(uuid='NNN'))
        self.assertEqual('[node: NNN]',
                         utils.processing_logger_prefix(node_info=node_info))

    def test_prefix_only_bmc(self):
        data = {'inventory': {'bmc_address': '1.2.3.4'}}
        self.assertEqual('[node: BMC 1.2.3.4]',
                         utils.processing_logger_prefix(data=data))

    def test_prefix_only_mac(self):
        data = {'boot_interface': '01-aa-bb-cc-dd-ee-ff'}
        self.assertEqual('[node: MAC aa:bb:cc:dd:ee:ff]',
                         utils.processing_logger_prefix(data=data))

    def test_prefix_everything(self):
        node_info = node.Node(mock.Mock(), dict(uuid='NNN'))
        data = {'boot_interface': '01-aa-bb-cc-dd-ee-ff',
                'inventory': {'bmc_address': '1.2.3.4'}}
        self.assertEqual('[node: NNN MAC aa:bb:cc:dd:ee:ff BMC 1.2.3.4]',
                         utils.processing_logger_prefix(node_info=node_info,
                                                        data=data))

    def test_prefix_uuid_not_str(self):
        node_info = node.Node(mock.Mock(), dict(uuid=None))
        self.assertEqual('[node: None]',
                         utils.processing_logger_prefix(node_info=node_info))

    def test_prefix_NodeInfo_instance(self):
        node_info = node_cache.NodeInfo('NNN')
        self.assertEqual('[node: NNN]',
                         utils.processing_logger_prefix(node_info=node_info))

    def test_prefix_NodeInfo_instance_with_state(self):
        node_info = node_cache.NodeInfo('NNN', state='foobar')
        self.assertEqual('[node: NNN state foobar]',
                         utils.processing_logger_prefix(node_info=node_info))

    def test_adapter_with_bmc(self):
        node_info = node.Node(mock.Mock(), dict(uuid='NNN'))
        data = {'boot_interface': '01-aa-bb-cc-dd-ee-ff',
                'inventory': {'bmc_address': '1.2.3.4'}}
        logger = utils.getProcessingLogger(__name__)
        msg, _kwargs = logger.process('foo', {'node_info': node_info,
                                              'data': data})
        self.assertEqual(
            '[node: NNN MAC aa:bb:cc:dd:ee:ff BMC 1.2.3.4] foo',
            msg)

    def test_adapter_empty_data(self):
        logger = utils.getProcessingLogger(__name__)
        msg, _kwargs = logger.process('foo', {'node_info': None,
                                              'data': None})
        self.assertEqual('[unidentified node] foo', msg)

    def test_adapter_no_data(self):
        logger = utils.getProcessingLogger(__name__)
        msg, _kwargs = logger.process('foo', {})
        self.assertEqual('foo', msg)


class TestIsoTimestamp(base.BaseTest):
    def test_ok(self):
        iso_date = '1970-01-01T00:00:00+00:00'
        self.assertEqual(iso_date, utils.iso_timestamp(0.0))

    def test_none(self):
        self.assertIsNone(utils.iso_timestamp(None))


@mock.patch.object(utils, 'coordination', autospec=True)
class TestGetCoordinator(base.BaseTest):
    def test_get(self, mock_coordination):
        CONF.set_override('backend_url', 'etcd3://1.2.3.4:2379',
                          'coordination')
        CONF.set_override('host', '1.2.3.5')
        utils.get_coordinator()
        mock_coordination.get_coordinator.assert_called_once_with(
            'etcd3://1.2.3.4:2379', b'1.2.3.5')
