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
import json
import unittest

import fixtures
import mock
import oslo_messaging as messaging
from oslo_utils import uuidutils

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector.common import rpc
from ironic_inspector.common import swift
import ironic_inspector.conf
from ironic_inspector.conf import opts as conf_opts
from ironic_inspector import introspection_state as istate
from ironic_inspector import main
from ironic_inspector import node_cache
from ironic_inspector.plugins import base as plugins_base
from ironic_inspector.plugins import example as example_plugin
from ironic_inspector.plugins import introspection_data as intros_data_plugin
from ironic_inspector import process
from ironic_inspector import rules
from ironic_inspector.test import base as test_base
from ironic_inspector import utils

CONF = ironic_inspector.conf.CONF


def _get_error(res):
    return json.loads(res.data.decode('utf-8'))['error']['message']


class BaseAPITest(test_base.BaseTest):
    def setUp(self):
        super(BaseAPITest, self).setUp()
        main.app.config['TESTING'] = True
        self.app = main.app.test_client()
        CONF.set_override('auth_strategy', 'noauth')
        self.uuid = uuidutils.generate_uuid()


class TestApiIntrospect(BaseAPITest):
    def setUp(self):
        super(TestApiIntrospect, self).setUp()
        self.rpc_get_client_mock = self.useFixture(
            fixtures.MockPatchObject(rpc, 'get_client', autospec=True)).mock
        self.client_mock = mock.MagicMock(spec=messaging.RPCClient)
        self.rpc_get_client_mock.return_value = self.client_mock

    def test_introspect_no_authentication(self):
        CONF.set_override('auth_strategy', 'noauth')

        res = self.app.post('/v1/introspection/%s' % self.uuid)

        self.assertEqual(202, res.status_code)
        self.client_mock.call.assert_called_once_with({}, 'do_introspection',
                                                      node_id=self.uuid,
                                                      manage_boot=True,
                                                      token=None)

    def test_intospect_failed(self):
        self.client_mock.call.side_effect = utils.Error("boom")
        res = self.app.post('/v1/introspection/%s' % self.uuid)

        self.assertEqual(400, res.status_code)
        self.assertEqual(
            'boom',
            json.loads(res.data.decode('utf-8'))['error']['message'])
        self.client_mock.call.assert_called_once_with({}, 'do_introspection',
                                                      node_id=self.uuid,
                                                      manage_boot=True,
                                                      token=None)

    def test_introspect_no_manage_boot(self):
        res = self.app.post('/v1/introspection/%s?manage_boot=0' % self.uuid)
        self.assertEqual(202, res.status_code)
        self.client_mock.call.assert_called_once_with({}, 'do_introspection',
                                                      node_id=self.uuid,
                                                      manage_boot=False,
                                                      token=None)

    def test_introspect_can_manage_boot_false(self):
        CONF.set_override('can_manage_boot', False)
        res = self.app.post('/v1/introspection/%s?manage_boot=0' % self.uuid)
        self.assertEqual(202, res.status_code)
        self.client_mock.call.assert_called_once_with({}, 'do_introspection',
                                                      node_id=self.uuid,
                                                      manage_boot=False,
                                                      token=None)

    def test_introspect_can_manage_boot_false_failed(self):
        CONF.set_override('can_manage_boot', False)
        res = self.app.post('/v1/introspection/%s' % self.uuid)
        self.assertEqual(400, res.status_code)
        self.assertFalse(self.client_mock.call.called)

    def test_introspect_wrong_manage_boot(self):
        res = self.app.post('/v1/introspection/%s?manage_boot=foo' % self.uuid)
        self.assertEqual(400, res.status_code)
        self.assertFalse(self.client_mock.call.called)
        self.assertEqual(
            'Invalid boolean value for manage_boot: foo',
            json.loads(res.data.decode('utf-8'))['error']['message'])

    @mock.patch.object(utils, 'check_auth', autospec=True)
    def test_introspect_failed_authentication(self, auth_mock):
        CONF.set_override('auth_strategy', 'keystone')
        auth_mock.side_effect = utils.Error('Boom', code=403)
        res = self.app.post('/v1/introspection/%s' % self.uuid,
                            headers={'X-Auth-Token': 'token'})
        self.assertEqual(403, res.status_code)
        self.assertFalse(self.client_mock.call.called)


@mock.patch.object(process, 'process', autospec=True)
class TestApiContinue(BaseAPITest):
    def test_continue(self, process_mock):
        # should be ignored
        CONF.set_override('auth_strategy', 'keystone')
        process_mock.return_value = {'result': 42}
        res = self.app.post('/v1/continue', data='{"foo": "bar"}')
        self.assertEqual(200, res.status_code)
        process_mock.assert_called_once_with({"foo": "bar"})
        self.assertEqual({"result": 42}, json.loads(res.data.decode()))

    def test_continue_failed(self, process_mock):
        process_mock.side_effect = utils.Error("boom")
        res = self.app.post('/v1/continue', data='{"foo": "bar"}')
        self.assertEqual(400, res.status_code)
        process_mock.assert_called_once_with({"foo": "bar"})
        self.assertEqual('boom', _get_error(res))

    def test_continue_wrong_type(self, process_mock):
        res = self.app.post('/v1/continue', data='42')
        self.assertEqual(400, res.status_code)
        self.assertEqual('Invalid data: expected a JSON object, got int',
                         _get_error(res))
        self.assertFalse(process_mock.called)


class TestApiAbort(BaseAPITest):
    def setUp(self):
        super(TestApiAbort, self).setUp()
        self.rpc_get_client_mock = self.useFixture(
            fixtures.MockPatchObject(rpc, 'get_client', autospec=True)).mock
        self.client_mock = mock.MagicMock(spec=messaging.RPCClient)
        self.rpc_get_client_mock.return_value = self.client_mock

    def test_ok(self):

        res = self.app.post('/v1/introspection/%s/abort' % self.uuid,
                            headers={'X-Auth-Token': 'token'})

        self.client_mock.call.assert_called_once_with({}, 'do_abort',
                                                      node_id=self.uuid,
                                                      token='token')
        self.assertEqual(202, res.status_code)
        self.assertEqual(b'', res.data)

    def test_no_authentication(self):

        res = self.app.post('/v1/introspection/%s/abort' % self.uuid)

        self.client_mock.call.assert_called_once_with({}, 'do_abort',
                                                      node_id=self.uuid,
                                                      token=None)
        self.assertEqual(202, res.status_code)
        self.assertEqual(b'', res.data)

    def test_node_not_found(self):
        exc = utils.Error("Not Found.", code=404)
        self.client_mock.call.side_effect = exc

        res = self.app.post('/v1/introspection/%s/abort' % self.uuid)

        self.client_mock.call.assert_called_once_with({}, 'do_abort',
                                                      node_id=self.uuid,
                                                      token=None)
        self.assertEqual(404, res.status_code)
        data = json.loads(str(res.data.decode()))
        self.assertEqual(str(exc), data['error']['message'])

    def test_abort_failed(self):
        exc = utils.Error("Locked.", code=409)
        self.client_mock.call.side_effect = exc

        res = self.app.post('/v1/introspection/%s/abort' % self.uuid)

        self.client_mock.call.assert_called_once_with({}, 'do_abort',
                                                      node_id=self.uuid,
                                                      token=None)
        self.assertEqual(409, res.status_code)
        data = json.loads(res.data.decode())
        self.assertEqual(str(exc), data['error']['message'])


class GetStatusAPIBaseTest(BaseAPITest):
    def setUp(self):
        super(GetStatusAPIBaseTest, self).setUp()
        self.uuid2 = uuidutils.generate_uuid()
        self.finished_node = node_cache.NodeInfo(
            uuid=self.uuid,
            started_at=datetime.datetime(1, 1, 1),
            finished_at=datetime.datetime(1, 1, 2),
            error='boom',
            state=istate.States.error)
        self.finished_node.links = [
            {u'href': u'http://localhost/v1/introspection/%s' %
             self.finished_node.uuid,
             u'rel': u'self'},
        ]
        self.finished_node.status = {
            'finished': True,
            'state': self.finished_node._state,
            'started_at': self.finished_node.started_at.isoformat(),
            'finished_at': self.finished_node.finished_at.isoformat(),
            'error': self.finished_node.error,
            'uuid': self.finished_node.uuid,
            'links': self.finished_node.links
        }

        self.unfinished_node = node_cache.NodeInfo(
            uuid=self.uuid2,
            started_at=datetime.datetime(1, 1, 1),
            state=istate.States.processing)
        self.unfinished_node.links = [
            {u'href': u'http://localhost/v1/introspection/%s' %
             self.unfinished_node.uuid,
             u'rel': u'self'}
        ]
        finished_at = (self.unfinished_node.finished_at.isoformat()
                       if self.unfinished_node.finished_at else None)
        self.unfinished_node.status = {
            'finished': False,
            'state': self.unfinished_node._state,
            'started_at': self.unfinished_node.started_at.isoformat(),
            'finished_at': finished_at,
            'error': None,
            'uuid': self.unfinished_node.uuid,
            'links': self.unfinished_node.links
        }


@mock.patch.object(node_cache, 'get_node', autospec=True)
class TestApiGetStatus(GetStatusAPIBaseTest):
    def test_get_introspection_in_progress(self, get_mock):
        get_mock.return_value = self.unfinished_node
        res = self.app.get('/v1/introspection/%s' % self.uuid)
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.unfinished_node.status,
                         json.loads(res.data.decode('utf-8')))

    def test_get_introspection_finished(self, get_mock):
        get_mock.return_value = self.finished_node
        res = self.app.get('/v1/introspection/%s' % self.uuid)
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.finished_node.status,
                         json.loads(res.data.decode('utf-8')))


@mock.patch.object(node_cache, 'get_node_list', autospec=True)
class TestApiListStatus(GetStatusAPIBaseTest):

    def test_list_introspection(self, list_mock):
        list_mock.return_value = [self.finished_node, self.unfinished_node]
        res = self.app.get('/v1/introspection')
        self.assertEqual(200, res.status_code)
        statuses = json.loads(res.data.decode('utf-8')).get('introspection')

        self.assertEqual([self.finished_node.status,
                          self.unfinished_node.status], statuses)
        list_mock.assert_called_once_with(marker=None,
                                          limit=CONF.api_max_limit)

    def test_list_introspection_limit(self, list_mock):
        res = self.app.get('/v1/introspection?limit=1000')
        self.assertEqual(200, res.status_code)
        list_mock.assert_called_once_with(marker=None, limit=1000)

    def test_list_introspection_makrer(self, list_mock):
        res = self.app.get('/v1/introspection?marker=%s' %
                           self.finished_node.uuid)
        self.assertEqual(200, res.status_code)
        list_mock.assert_called_once_with(marker=self.finished_node.uuid,
                                          limit=CONF.api_max_limit)


class TestApiGetData(BaseAPITest):
    def setUp(self):
        super(TestApiGetData, self).setUp()
        self.introspection_data = {
            'ipmi_address': '1.2.3.4',
            'cpus': 2,
            'cpu_arch': 'x86_64',
            'memory_mb': 1024,
            'local_gb': 20,
            'interfaces': {
                'em1': {'mac': '11:22:33:44:55:66', 'ip': '1.2.0.1'},
            }
        }

    @mock.patch.object(swift, 'SwiftAPI', autospec=True)
    def test_get_introspection_data_from_swift(self, swift_mock):
        CONF.set_override('store_data', 'swift', 'processing')
        swift_conn = swift_mock.return_value
        swift_conn.get_object.return_value = json.dumps(
            self.introspection_data)
        res = self.app.get('/v1/introspection/%s/data' % self.uuid)
        name = 'inspector_data-%s' % self.uuid
        swift_conn.get_object.assert_called_once_with(name)
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.introspection_data,
                         json.loads(res.data.decode('utf-8')))

    @mock.patch.object(intros_data_plugin, 'DatabaseStore',
                       autospec=True)
    def test_get_introspection_data_from_db(self, db_mock):
        CONF.set_override('store_data', 'database', 'processing')
        db_store = db_mock.return_value
        db_store.get.return_value = json.dumps(self.introspection_data)
        res = self.app.get('/v1/introspection/%s/data' % self.uuid)
        db_store.get.assert_called_once_with(self.uuid, processed=True,
                                             get_json=False)
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.introspection_data,
                         json.loads(res.data.decode('utf-8')))

    def test_introspection_data_not_stored(self):
        CONF.set_override('store_data', 'none', 'processing')
        res = self.app.get('/v1/introspection/%s/data' % self.uuid)
        self.assertEqual(404, res.status_code)

    @mock.patch.object(ir_utils, 'get_node', autospec=True)
    @mock.patch.object(main.process, 'get_introspection_data', autospec=True)
    def test_with_name(self, process_mock, get_mock):
        get_mock.return_value = mock.Mock(uuid=self.uuid)
        CONF.set_override('store_data', 'swift', 'processing')
        process_mock.return_value = json.dumps(self.introspection_data)
        res = self.app.get('/v1/introspection/name1/data')
        self.assertEqual(200, res.status_code)
        self.assertEqual(self.introspection_data,
                         json.loads(res.data.decode('utf-8')))
        get_mock.assert_called_once_with('name1', fields=['uuid'])


class TestApiReapply(BaseAPITest):

    def setUp(self):
        super(TestApiReapply, self).setUp()
        self.rpc_get_client_mock = self.useFixture(
            fixtures.MockPatchObject(rpc, 'get_client', autospec=True)).mock
        self.client_mock = mock.MagicMock(spec=messaging.RPCClient)
        self.rpc_get_client_mock.return_value = self.client_mock
        CONF.set_override('store_data', 'swift', 'processing')

    def test_api_ok(self):
        self.app.post('/v1/introspection/%s/data/unprocessed' %
                      self.uuid)
        self.client_mock.call.assert_called_once_with({}, 'do_reapply',
                                                      node_uuid=self.uuid,
                                                      data=None)

    def test_user_data(self):
        res = self.app.post('/v1/introspection/%s/data/unprocessed' %
                            self.uuid, data='some data')
        self.assertEqual(400, res.status_code)
        message = json.loads(res.data.decode())['error']['message']
        self.assertIn('Invalid data: expected a JSON object', message)
        self.assertFalse(self.client_mock.call.called)

    def test_user_data_valid(self):
        data = {"foo": "bar"}
        res = self.app.post('/v1/introspection/%s/data/unprocessed' %
                            self.uuid, data=json.dumps(data))
        self.assertEqual(202, res.status_code)
        self.client_mock.call.assert_called_once_with({}, 'do_reapply',
                                                      node_uuid=self.uuid,
                                                      data=data)

    def test_get_introspection_data_error(self):
        exc = utils.Error('The store is crashed', code=404)
        self.client_mock.call.side_effect = exc

        res = self.app.post('/v1/introspection/%s/data/unprocessed' %
                            self.uuid)

        self.assertEqual(404, res.status_code)
        message = json.loads(res.data.decode())['error']['message']
        self.assertEqual(str(exc), message)
        self.client_mock.call.assert_called_once_with({}, 'do_reapply',
                                                      node_uuid=self.uuid,
                                                      data=None)

    def test_generic_error(self):
        exc = utils.Error('Oops', code=400)
        self.client_mock.call.side_effect = exc

        res = self.app.post('/v1/introspection/%s/data/unprocessed' %
                            self.uuid)

        self.assertEqual(400, res.status_code)
        message = json.loads(res.data.decode())['error']['message']
        self.assertEqual(str(exc), message)
        self.client_mock.call.assert_called_once_with({}, 'do_reapply',
                                                      node_uuid=self.uuid,
                                                      data=None)

    @mock.patch.object(ir_utils, 'get_node', autospec=True)
    def test_reapply_with_node_name(self, get_mock):
        get_mock.return_value = mock.Mock(uuid=self.uuid)
        self.app.post('/v1/introspection/%s/data/unprocessed' %
                      'fake-node')
        self.client_mock.call.assert_called_once_with({}, 'do_reapply',
                                                      node_uuid=self.uuid,
                                                      data=None)
        get_mock.assert_called_once_with('fake-node', fields=['uuid'])


class TestApiRules(BaseAPITest):
    @mock.patch.object(rules, 'get_all')
    def test_get_all(self, get_all_mock):
        get_all_mock.return_value = [
            mock.Mock(spec=rules.IntrospectionRule,
                      **{'as_dict.return_value': {'uuid': 'foo'}}),
            mock.Mock(spec=rules.IntrospectionRule,
                      **{'as_dict.return_value': {'uuid': 'bar'}}),
        ]

        res = self.app.get('/v1/rules')
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            {
                'rules': [{'uuid': 'foo',
                           'links': [
                               {'href': '/v1/rules/foo', 'rel': 'self'}
                           ]},
                          {'uuid': 'bar',
                           'links': [
                               {'href': '/v1/rules/bar', 'rel': 'self'}
                           ]}]
            },
            json.loads(res.data.decode('utf-8')))
        get_all_mock.assert_called_once_with()
        for m in get_all_mock.return_value:
            m.as_dict.assert_called_with(short=True)

    @mock.patch.object(rules, 'delete_all')
    def test_delete_all(self, delete_all_mock):
        res = self.app.delete('/v1/rules')
        self.assertEqual(204, res.status_code)
        delete_all_mock.assert_called_once_with()

    @mock.patch.object(rules, 'create', autospec=True)
    def test_create(self, create_mock):
        data = {'uuid': self.uuid,
                'conditions': 'cond',
                'actions': 'act'}
        exp = data.copy()
        exp['description'] = None
        create_mock.return_value = mock.Mock(spec=rules.IntrospectionRule,
                                             **{'as_dict.return_value': exp})

        res = self.app.post('/v1/rules', data=json.dumps(data))
        self.assertEqual(201, res.status_code)
        create_mock.assert_called_once_with(conditions_json='cond',
                                            actions_json='act',
                                            uuid=self.uuid,
                                            description=None)
        self.assertEqual(exp, json.loads(res.data.decode('utf-8')))

    @mock.patch.object(rules, 'create', autospec=True)
    def test_create_api_less_1_6(self, create_mock):
        data = {'uuid': self.uuid,
                'conditions': 'cond',
                'actions': 'act'}
        exp = data.copy()
        exp['description'] = None
        create_mock.return_value = mock.Mock(spec=rules.IntrospectionRule,
                                             **{'as_dict.return_value': exp})

        headers = {conf_opts.VERSION_HEADER:
                   main._format_version((1, 5))}

        res = self.app.post('/v1/rules', data=json.dumps(data),
                            headers=headers)
        self.assertEqual(200, res.status_code)
        create_mock.assert_called_once_with(conditions_json='cond',
                                            actions_json='act',
                                            uuid=self.uuid,
                                            description=None)
        self.assertEqual(exp, json.loads(res.data.decode('utf-8')))

    @mock.patch.object(rules, 'create', autospec=True)
    def test_create_bad_uuid(self, create_mock):
        data = {'uuid': 'foo',
                'conditions': 'cond',
                'actions': 'act'}

        res = self.app.post('/v1/rules', data=json.dumps(data))
        self.assertEqual(400, res.status_code)

    @mock.patch.object(rules, 'get')
    def test_get_one(self, get_mock):
        get_mock.return_value = mock.Mock(spec=rules.IntrospectionRule,
                                          **{'as_dict.return_value':
                                             {'uuid': 'foo'}})

        res = self.app.get('/v1/rules/' + self.uuid)
        self.assertEqual(200, res.status_code)
        self.assertEqual({'uuid': 'foo',
                          'links': [
                              {'href': '/v1/rules/foo', 'rel': 'self'}
                          ]},
                         json.loads(res.data.decode('utf-8')))
        get_mock.assert_called_once_with(self.uuid)
        get_mock.return_value.as_dict.assert_called_once_with(short=False)

    @mock.patch.object(rules, 'delete')
    def test_delete_one(self, delete_mock):
        res = self.app.delete('/v1/rules/' + self.uuid)
        self.assertEqual(204, res.status_code)
        delete_mock.assert_called_once_with(self.uuid)


class TestApiMisc(BaseAPITest):
    @mock.patch.object(node_cache, 'get_node', autospec=True)
    def test_404_expected(self, get_mock):
        get_mock.side_effect = utils.Error('boom', code=404)
        res = self.app.get('/v1/introspection/%s' % self.uuid)
        self.assertEqual(404, res.status_code)
        self.assertEqual('boom', _get_error(res))

    def test_404_unexpected(self):
        res = self.app.get('/v42')
        self.assertEqual(404, res.status_code)
        self.assertIn('not found', _get_error(res).lower())

    @mock.patch.object(node_cache, 'get_node', autospec=True)
    def test_500_with_debug(self, get_mock):
        CONF.set_override('debug', True)
        get_mock.side_effect = RuntimeError('boom')
        res = self.app.get('/v1/introspection/%s' % self.uuid)
        self.assertEqual(500, res.status_code)
        self.assertEqual('Internal server error (RuntimeError): boom',
                         _get_error(res))

    @mock.patch.object(node_cache, 'get_node', autospec=True)
    def test_500_without_debug(self, get_mock):
        CONF.set_override('debug', False)
        get_mock.side_effect = RuntimeError('boom')
        res = self.app.get('/v1/introspection/%s' % self.uuid)
        self.assertEqual(500, res.status_code)
        self.assertEqual('Internal server error',
                         _get_error(res))


class TestApiVersions(BaseAPITest):
    def _check_version_present(self, res):
        self.assertEqual('%d.%d' % main.MINIMUM_API_VERSION,
                         res.headers.get(conf_opts.MIN_VERSION_HEADER))
        self.assertEqual('%d.%d' % main.CURRENT_API_VERSION,
                         res.headers.get(conf_opts.MAX_VERSION_HEADER))

    def test_root_endpoint(self):
        res = self.app.get("/")
        self.assertEqual(200, res.status_code)
        self._check_version_present(res)
        data = res.data.decode('utf-8')
        json_data = json.loads(data)
        expected = {"versions": [{
            "status": "CURRENT", "id": '%s.%s' % main.CURRENT_API_VERSION,
            "links": [{
                "rel": "self",
                "href": ("http://localhost/v%s" %
                         main.CURRENT_API_VERSION[0])
            }]
        }]}
        self.assertEqual(expected, json_data)

    @mock.patch.object(main.app.url_map, "iter_rules", autospec=True)
    def test_version_endpoint(self, mock_rules):
        mock_rules.return_value = ["/v1/endpoint1", "/v1/endpoint2/<uuid>",
                                   "/v1/endpoint1/<name>",
                                   "/v2/endpoint1", "/v1/endpoint3",
                                   "/v1/endpoint2/<uuid>/subpoint"]
        endpoint = "/v1"
        res = self.app.get(endpoint)
        self.assertEqual(200, res.status_code)
        self._check_version_present(res)
        json_data = json.loads(res.data.decode('utf-8'))
        expected = {u'resources': [
            {
                u'name': u'endpoint1',
                u'links': [{
                    u'rel': u'self',
                    u'href': u'http://localhost/v1/endpoint1'}]
            },
            {
                u'name': u'endpoint3',
                u'links': [{
                    u'rel': u'self',
                    u'href': u'http://localhost/v1/endpoint3'}]
            },
        ]}
        self.assertEqual(expected, json_data)

    def test_version_endpoint_invalid(self):
        endpoint = "/v-1"
        res = self.app.get(endpoint)
        self.assertEqual(404, res.status_code)

    def test_404_unexpected(self):
        # API version on unknown pages
        self._check_version_present(self.app.get('/v1/foobar'))

    @mock.patch.object(rpc, 'get_client', autospec=True)
    @mock.patch.object(node_cache, 'get_node', autospec=True)
    def test_usual_requests(self, get_mock, rpc_mock):
        client_mock = mock.MagicMock(spec=messaging.RPCClient)
        rpc_mock.return_value = client_mock
        get_mock.return_value = node_cache.NodeInfo(uuid=self.uuid,
                                                    started_at=42.0)
        # Successful
        self._check_version_present(
            self.app.post('/v1/introspection/%s' % self.uuid))
        # With error
        self._check_version_present(
            self.app.post('/v1/introspection/foobar'))

    def test_request_correct_version(self):
        headers = {conf_opts.VERSION_HEADER:
                   main._format_version(main.CURRENT_API_VERSION)}
        self._check_version_present(self.app.get('/', headers=headers))

    def test_request_unsupported_version(self):
        bad_version = (main.CURRENT_API_VERSION[0],
                       main.CURRENT_API_VERSION[1] + 1)
        headers = {conf_opts.VERSION_HEADER:
                   main._format_version(bad_version)}
        res = self.app.get('/', headers=headers)
        self._check_version_present(res)
        self.assertEqual(406, res.status_code)
        error = _get_error(res)
        self.assertIn('%d.%d' % bad_version, error)
        self.assertIn('%d.%d' % main.MINIMUM_API_VERSION, error)
        self.assertIn('%d.%d' % main.CURRENT_API_VERSION, error)

    def test_request_latest_version(self):
        headers = {conf_opts.VERSION_HEADER: 'latest'}
        res = self.app.get('/', headers=headers)
        self.assertEqual(200, res.status_code)
        self._check_version_present(res)


class TestPlugins(unittest.TestCase):
    @mock.patch.object(example_plugin.ExampleProcessingHook,
                       'before_processing', autospec=True)
    @mock.patch.object(example_plugin.ExampleProcessingHook,
                       'before_update', autospec=True)
    def test_hook(self, mock_post, mock_pre):
        CONF.set_override('processing_hooks', 'example', 'processing')
        mgr = plugins_base.processing_hooks_manager()
        mgr.map_method('before_processing', 'introspection_data')
        mock_pre.assert_called_once_with(mock.ANY, 'introspection_data')
        mgr.map_method('before_update', 'node_info', {})
        mock_post.assert_called_once_with(mock.ANY, 'node_info', {})

    def test_manager_is_cached(self):
        self.assertIs(plugins_base.processing_hooks_manager(),
                      plugins_base.processing_hooks_manager())
