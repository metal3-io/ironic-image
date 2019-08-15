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

import eventlet

import contextlib  # noqa
import copy
import datetime
import json
import os
import sys
import tempfile
import time
import unittest

import fixtures
import mock
from oslo_config import cfg
from oslo_config import fixture as config_fixture
from oslo_utils import timeutils
from oslo_utils import uuidutils
import pytz
import requests
import six
from six.moves import urllib

from ironic_inspector.cmd import all as inspector_cmd
from ironic_inspector.cmd import dbsync
from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import db
from ironic_inspector import introspection_state as istate
from ironic_inspector import main
from ironic_inspector import node_cache
from ironic_inspector import rules
from ironic_inspector.test import base
from ironic_inspector.test.unit import test_rules

eventlet.monkey_patch()

CONF = """
[ironic]
auth_type=none
endpoint_override=http://url
[pxe_filter]
driver = noop
[DEFAULT]
debug = True
introspection_delay = 0
auth_strategy=noauth
transport_url=fake://
[database]
connection = sqlite:///%(db_file)s
[processing]
processing_hooks=$default_processing_hooks,lldp_basic
store_data = database
"""


DEFAULT_SLEEP = 2
TEST_CONF_FILE = None


def get_test_conf_file():
    global TEST_CONF_FILE
    if not TEST_CONF_FILE:
        d = tempfile.mkdtemp()
        TEST_CONF_FILE = os.path.join(d, 'test.conf')
        db_file = os.path.join(d, 'test.db')
        with open(TEST_CONF_FILE, 'wb') as fp:
            content = CONF % {'db_file': db_file}
            fp.write(content.encode('utf-8'))
    return TEST_CONF_FILE


def get_error(response):
    return response.json()['error']['message']


def _query_string(*field_names):
    def outer(func):
        @six.wraps(func)
        def inner(*args, **kwargs):
            queries = []
            for field_name in field_names:
                field = kwargs.pop(field_name, None)
                if field is not None:
                    queries.append('%s=%s' % (field_name, field))

            query_string = '&'.join(queries)
            if query_string:
                query_string = '?' + query_string
            return func(*args, query_string=query_string, **kwargs)
        return inner
    return outer


class Base(base.NodeTest):
    ROOT_URL = 'http://127.0.0.1:5050'
    IS_FUNCTIONAL = True

    def setUp(self):
        super(Base, self).setUp()
        rules.delete_all()

        self.cli_fixture = self.useFixture(
            fixtures.MockPatchObject(ir_utils, 'get_client'))
        self.cli = self.cli_fixture.mock.return_value
        self.cli.node.get.return_value = self.node
        self.cli.node.update.return_value = self.node
        self.cli.node.list.return_value = [self.node]

        self.patch = [
            {'op': 'add', 'path': '/properties/cpus', 'value': '4'},
            {'path': '/properties/cpu_arch', 'value': 'x86_64', 'op': 'add'},
            {'op': 'add', 'path': '/properties/memory_mb', 'value': '12288'},
            {'path': '/properties/local_gb', 'value': '999', 'op': 'add'}
        ]
        self.patch_root_hints = [
            {'op': 'add', 'path': '/properties/cpus', 'value': '4'},
            {'path': '/properties/cpu_arch', 'value': 'x86_64', 'op': 'add'},
            {'op': 'add', 'path': '/properties/memory_mb', 'value': '12288'},
            {'path': '/properties/local_gb', 'value': '19', 'op': 'add'}
        ]

        self.node.power_state = 'power off'

        self.cfg = self.useFixture(config_fixture.Config())
        conf_file = get_test_conf_file()
        self.cfg.set_config_files([conf_file])

        # FIXME(milan) FakeListener.poll calls time.sleep() which leads to
        # busy polling with no sleep at all, effectively blocking the whole
        # process by consuming all CPU cycles in a single thread. MonkeyPatch
        # with eventlet.sleep seems to help this.
        self.useFixture(fixtures.MonkeyPatch(
            'oslo_messaging._drivers.impl_fake.time.sleep', eventlet.sleep))

    def tearDown(self):
        super(Base, self).tearDown()
        node_cache._delete_node(self.uuid)

    def call(self, method, endpoint, data=None, expect_error=None,
             api_version=None):
        if data is not None:
            data = json.dumps(data)
        endpoint = self.ROOT_URL + endpoint
        headers = {'X-Auth-Token': 'token'}
        if api_version:
            headers[main._VERSION_HEADER] = '%d.%d' % api_version
        res = getattr(requests, method.lower())(endpoint, data=data,
                                                headers=headers)
        if expect_error:
            self.assertEqual(expect_error, res.status_code)
        else:
            if res.status_code >= 400:
                msg = ('%(meth)s %(url)s failed with code %(code)s: %(msg)s' %
                       {'meth': method.upper(), 'url': endpoint,
                        'code': res.status_code, 'msg': get_error(res)})
                raise AssertionError(msg)
        return res

    def call_introspect(self, uuid, manage_boot=True, **kwargs):
        endpoint = '/v1/introspection/%s' % uuid
        if manage_boot is not None:
            endpoint = '%s?manage_boot=%s' % (endpoint, manage_boot)
        return self.call('post', endpoint)

    def call_get_status(self, uuid, **kwargs):
        return self.call('get', '/v1/introspection/%s' % uuid, **kwargs).json()

    def call_get_data(self, uuid, **kwargs):
        return self.call('get', '/v1/introspection/%s/data' % uuid,
                         **kwargs).json()

    @_query_string('marker', 'limit')
    def call_get_statuses(self, query_string='', **kwargs):
        path = '/v1/introspection'
        return self.call('get', path + query_string, **kwargs).json()

    def call_abort_introspect(self, uuid, **kwargs):
        return self.call('post', '/v1/introspection/%s/abort' % uuid, **kwargs)

    def call_reapply(self, uuid, **kwargs):
        return self.call('post', '/v1/introspection/%s/data/unprocessed' %
                         uuid, **kwargs)

    def call_continue(self, data, **kwargs):
        return self.call('post', '/v1/continue', data=data, **kwargs).json()

    def call_add_rule(self, data, **kwargs):
        return self.call('post', '/v1/rules', data=data, **kwargs).json()

    def call_list_rules(self, **kwargs):
        return self.call('get', '/v1/rules', **kwargs).json()['rules']

    def call_delete_rules(self, **kwargs):
        self.call('delete', '/v1/rules', **kwargs)

    def call_delete_rule(self, uuid, **kwargs):
        self.call('delete', '/v1/rules/' + uuid, **kwargs)

    def call_get_rule(self, uuid, **kwargs):
        return self.call('get', '/v1/rules/' + uuid, **kwargs).json()

    def _fake_status(self, finished=mock.ANY, state=mock.ANY, error=mock.ANY,
                     started_at=mock.ANY, finished_at=mock.ANY,
                     links=mock.ANY):
        return {'uuid': self.uuid, 'finished': finished, 'error': error,
                'state': state, 'finished_at': finished_at,
                'started_at': started_at,
                'links': [{u'href': u'%s/v1/introspection/%s' % (self.ROOT_URL,
                                                                 self.uuid),
                           u'rel': u'self'}]}

    def check_status(self, status, finished, state, error=None):
        self.assertEqual(
            self._fake_status(finished=finished,
                              state=state,
                              finished_at=finished and mock.ANY or None,
                              error=error),
            status
        )
        curr_time = datetime.datetime.fromtimestamp(
            time.time(), tz=pytz.timezone(time.tzname[0]))
        started_at = timeutils.parse_isotime(status['started_at'])
        self.assertLess(started_at, curr_time)
        if finished:
            finished_at = timeutils.parse_isotime(status['finished_at'])
            self.assertLess(started_at, finished_at)
            self.assertLess(finished_at, curr_time)
        else:
            self.assertIsNone(status['finished_at'])

    def db_row(self):
        """return database row matching self.uuid."""
        return db.model_query(db.Node).get(self.uuid)


class Test(Base):
    def test_bmc(self):
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid,
                                                              'reboot')

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.cli.node.update.assert_called_with(self.uuid, mock.ANY)
        self.assertCalledWithPatch(self.patch, self.cli.node.update)
        self.cli.port.create.assert_called_once_with(
            node_uuid=self.uuid, address='11:22:33:44:55:66', extra={},
            pxe_enabled=True)
        self.assertTrue(self.cli.node.set_boot_device.called)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

    def test_port_creation_update_and_deletion(self):
        cfg.CONF.set_override('add_ports', 'active', 'processing')
        cfg.CONF.set_override('keep_ports', 'added', 'processing')

        uuid_to_delete = uuidutils.generate_uuid()
        uuid_to_update = uuidutils.generate_uuid()
        # Two ports already exist: one with incorrect pxe_enabled, the other
        # should be deleted.
        self.cli.node.list_ports.return_value = [
            mock.Mock(address=self.macs[1], uuid=uuid_to_update,
                      node_uuid=self.uuid, extra={}, pxe_enabled=True),
            mock.Mock(address='foobar', uuid=uuid_to_delete,
                      node_uuid=self.uuid, extra={}, pxe_enabled=True),
        ]
        # Two more ports are created, one with client_id. Make sure the
        # returned object has the same properties as requested in create().
        self.cli.port.create.side_effect = mock.Mock

        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid,
                                                              'reboot')

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.cli.node.update.assert_called_with(self.uuid, mock.ANY)
        self.assertCalledWithPatch(self.patch, self.cli.node.update)
        calls = [
            mock.call(node_uuid=self.uuid, address=self.macs[0],
                      extra={}, pxe_enabled=True),
            mock.call(node_uuid=self.uuid, address=self.macs[2],
                      extra={'client-id': self.client_id}, pxe_enabled=False),
        ]
        self.cli.port.create.assert_has_calls(calls, any_order=True)
        self.cli.port.delete.assert_called_once_with(uuid_to_delete)
        self.cli.port.update.assert_called_once_with(
            uuid_to_update,
            [{'op': 'replace', 'path': '/pxe_enabled', 'value': False}])

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

    def test_introspection_statuses(self):
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        # NOTE(zhenguo): only test finished=False here, as we don't know
        # other nodes status in this thread.
        statuses = self.call_get_statuses().get('introspection')
        self.assertIn(self._fake_status(finished=False), statuses)

        # check we've got 1 status with a limit of 1
        statuses = self.call_get_statuses(limit=1).get('introspection')
        self.assertEqual(1, len(statuses))

        all_statuses = self.call_get_statuses().get('introspection')
        marker_statuses = self.call_get_statuses(
            marker=self.uuid, limit=1).get('introspection')
        marker_index = all_statuses.index(self.call_get_status(self.uuid))
        # marker is the last row on previous page
        self.assertEqual(all_statuses[marker_index+1:marker_index+2],
                         marker_statuses)

        self.call_continue(self.data)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

        # fetch all statuses and db nodes to assert pagination
        statuses = self.call_get_statuses().get('introspection')
        nodes = db.model_query(db.Node).order_by(
            db.Node.started_at.desc()).all()

        # assert ordering
        self.assertEqual([node.uuid for node in nodes],
                         [status_.get('uuid') for status_ in statuses])

        # assert pagination
        half = len(nodes) // 2
        marker = nodes[half].uuid
        statuses = self.call_get_statuses(marker=marker).get('introspection')
        self.assertEqual([node.uuid for node in nodes[half + 1:]],
                         [status_.get('uuid') for status_ in statuses])

        # assert status links work
        self.assertEqual([self.call_get_status(status_.get('uuid'))
                          for status_ in statuses],
                         [self.call('GET', urllib.parse.urlparse(
                             status_.get('links')[0].get('href')).path).json()
                          for status_ in statuses])

    def test_manage_boot(self):
        self.call_introspect(self.uuid, manage_boot=False)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.assertFalse(self.cli.node.set_power_state.called)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.cli.node.update.assert_called_with(self.uuid, mock.ANY)
        self.assertFalse(self.cli.node.set_boot_device.called)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

    def test_rules_api(self):
        res = self.call_list_rules()
        self.assertEqual([], res)

        rule = {
            'conditions': [
                {'op': 'eq', 'field': 'memory_mb', 'value': 1024},
            ],
            'actions': [{'action': 'fail', 'message': 'boom'}],
            'description': 'Cool actions'
        }

        res = self.call_add_rule(rule)
        self.assertTrue(res['uuid'])
        rule['uuid'] = res['uuid']
        rule['links'] = res['links']
        rule['conditions'] = [
            test_rules.BaseTest.condition_defaults(rule['conditions'][0]),
        ]
        self.assertEqual(rule, res)

        res = self.call('get', rule['links'][0]['href']).json()
        self.assertEqual(rule, res)

        res = self.call_list_rules()
        self.assertEqual(rule['links'], res[0].pop('links'))
        self.assertEqual([{'uuid': rule['uuid'],
                           'description': 'Cool actions'}],
                         res)

        res = self.call_get_rule(rule['uuid'])
        self.assertEqual(rule, res)

        self.call_delete_rule(rule['uuid'])
        res = self.call_list_rules()
        self.assertEqual([], res)

        links = rule.pop('links')
        del rule['uuid']
        for _ in range(3):
            self.call_add_rule(rule)

        res = self.call_list_rules()
        self.assertEqual(3, len(res))

        self.call_delete_rules()
        res = self.call_list_rules()
        self.assertEqual([], res)

        self.call('get', links[0]['href'], expect_error=404)
        self.call('delete', links[0]['href'], expect_error=404)

    def test_introspection_rules(self):
        self.node.extra['bar'] = 'foo'
        rules = [
            {
                'conditions': [
                    {'field': 'memory_mb', 'op': 'eq', 'value': 12288},
                    {'field': 'local_gb', 'op': 'gt', 'value': 998},
                    {'field': 'local_gb', 'op': 'lt', 'value': 1000},
                    {'field': 'local_gb', 'op': 'matches', 'value': '[0-9]+'},
                    {'field': 'cpu_arch', 'op': 'contains', 'value': '[0-9]+'},
                    {'field': 'root_disk.wwn', 'op': 'is-empty'},
                    {'field': 'inventory.interfaces[*].ipv4_address',
                     'op': 'contains', 'value': r'127\.0\.0\.1',
                     'invert': True, 'multiple': 'all'},
                    {'field': 'i.do.not.exist', 'op': 'is-empty'},
                ],
                'actions': [
                    {'action': 'set-attribute', 'path': '/extra/foo',
                     'value': 'bar'}
                ]
            },
            {
                'conditions': [
                    {'field': 'memory_mb', 'op': 'ge', 'value': 100500},
                ],
                'actions': [
                    {'action': 'set-attribute', 'path': '/extra/bar',
                     'value': 'foo'},
                    {'action': 'fail', 'message': 'boom'}
                ]
            }
        ]
        for rule in rules:
            self.call_add_rule(rule)

        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.call_continue(self.data)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.cli.node.update.assert_any_call(
            self.uuid,
            [{'op': 'add', 'path': '/extra/foo', 'value': 'bar'}])

    def test_conditions_scheme_actions_path(self):
        rules = [
            {
                'conditions': [
                    {'field': 'node://properties.local_gb', 'op': 'eq',
                     'value': 40},
                    {'field': 'node://driver_info.ipmi_address', 'op': 'eq',
                     'value': self.bmc_address},
                ],
                'actions': [
                    {'action': 'set-attribute', 'path': '/extra/foo',
                     'value': 'bar'}
                ]
            },
            {
                'conditions': [
                    {'field': 'data://inventory.cpu.count', 'op': 'eq',
                     'value': self.data['inventory']['cpu']['count']},
                ],
                'actions': [
                    {'action': 'set-attribute',
                     'path': '/driver_info/ipmi_address',
                     'value': '{data[inventory][bmc_address]}'}
                ]
            }
        ]
        for rule in rules:
            self.call_add_rule(rule)

        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.call_continue(self.data)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.cli.node.update.assert_any_call(
            self.uuid,
            [{'op': 'add', 'path': '/extra/foo', 'value': 'bar'}])

        self.cli.node.update.assert_any_call(
            self.uuid,
            [{'op': 'add', 'path': '/driver_info/ipmi_address',
              'value': self.data['inventory']['bmc_address']}])

    def test_root_device_hints(self):
        self.node.properties['root_device'] = {'size': 20}

        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid,
                                                              'reboot')

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.assertCalledWithPatch(self.patch_root_hints, self.cli.node.update)
        self.cli.port.create.assert_called_once_with(
            node_uuid=self.uuid, address='11:22:33:44:55:66', extra={},
            pxe_enabled=True)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

    def test_abort_introspection(self):
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid,
                                                              'reboot')
        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        res = self.call_abort_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.assertEqual(202, res.status_code)
        status = self.call_get_status(self.uuid)
        self.assertTrue(status['finished'])
        self.assertEqual('Canceled by operator', status['error'])

        # Note(mkovacik): we're checking just this doesn't pass OK as
        # there might be either a race condition (hard to test) that
        # yields a 'Node already finished.' or an attribute-based
        # look-up error from some pre-processing hooks because
        # node_info.finished() deletes the look-up attributes only
        # after releasing the node lock
        self.call('post', '/v1/continue', self.data, expect_error=400)

    def test_stored_data_processing(self):
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid,
                                                              'reboot')

        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        status = self.call_get_status(self.uuid)
        inspect_started_at = timeutils.parse_isotime(status['started_at'])
        self.check_status(status, finished=True, state=istate.States.finished)

        data = self.call_get_data(self.uuid)
        self.assertEqual(self.data['inventory'], data['inventory'])

        res = self.call_reapply(self.uuid)
        self.assertEqual(202, res.status_code)
        self.assertEqual('', res.text)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

        # checks the started_at updated in DB is correct
        reapply_started_at = timeutils.parse_isotime(status['started_at'])
        self.assertLess(inspect_started_at, reapply_started_at)

        # second reapply call
        res = self.call_reapply(self.uuid)
        self.assertEqual(202, res.status_code)
        self.assertEqual('', res.text)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        # Reapply with provided data
        new_data = copy.deepcopy(self.data)
        new_data['inventory']['cpu']['count'] = 42
        res = self.call_reapply(self.uuid, data=new_data)
        self.assertEqual(202, res.status_code)
        self.assertEqual('', res.text)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.check_status(status, finished=True, state=istate.States.finished)

        data = self.call_get_data(self.uuid)
        self.assertEqual(42, data['inventory']['cpu']['count'])

    def test_edge_state_transitions(self):
        """Assert state transitions work as expected in edge conditions."""
        # multiple introspect calls
        self.call_introspect(self.uuid)
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        # an error -start-> starting state transition is possible
        self.call_abort_introspect(self.uuid)
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        # double abort works
        self.call_abort_introspect(self.uuid)
        status = self.call_get_status(self.uuid)
        error = status['error']
        self.check_status(status, finished=True, state=istate.States.error,
                          error=error)
        self.call_abort_introspect(self.uuid)
        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.error,
                          error=error)

        # preventing stale data race condition
        # waiting -> processing is a strict state transition
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        row = self.db_row()
        row.state = istate.States.processing
        with db.ensure_transaction() as session:
            row.save(session)
        self.call_continue(self.data, expect_error=400)
        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.error,
                          error=mock.ANY)
        self.assertIn('no defined transition', status['error'])
        # multiple reapply calls
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.call_continue(self.data)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.call_reapply(self.uuid)
        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished,
                          error=None)
        self.call_reapply(self.uuid)
        # assert an finished -reapply-> reapplying -> finished state transition
        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished,
                          error=None)

    def test_without_root_disk(self):
        del self.data['root_disk']
        self.inventory['disks'] = []
        self.patch[-1] = {'path': '/properties/local_gb',
                          'value': '0', 'op': 'add'}

        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid,
                                                              'reboot')

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.cli.node.update.assert_called_with(self.uuid, mock.ANY)
        self.assertCalledWithPatch(self.patch, self.cli.node.update)
        self.cli.port.create.assert_called_once_with(
            node_uuid=self.uuid, extra={}, address='11:22:33:44:55:66',
            pxe_enabled=True)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

    def test_lldp_plugin(self):
        self.call_introspect(self.uuid)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)
        self.cli.node.set_power_state.assert_called_once_with(self.uuid,
                                                              'reboot')

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=False, state=istate.States.waiting)

        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

        updated_data = self.call_get_data(self.uuid)
        lldp_out = updated_data['all_interfaces']['eth1']

        expected_chassis_id = "11:22:33:aa:bb:cc"
        expected_port_id = "734"
        self.assertEqual(expected_chassis_id,
                         lldp_out['lldp_processed']['switch_chassis_id'])
        self.assertEqual(expected_port_id,
                         lldp_out['lldp_processed']['switch_port_id'])

    def test_update_unknown_active_node(self):
        cfg.CONF.set_override('permit_active_introspection', True,
                              'processing')
        self.node.provision_state = 'active'
        self.cli.node.list_ports.return_value = [
            mock.Mock(address='11:22:33:44:55:66', node_uuid=self.node.uuid)
        ]

        # NOTE(dtantsur): we're not starting introspection in this test.
        res = self.call_continue(self.data)
        self.assertEqual({'uuid': self.uuid}, res)
        eventlet.greenthread.sleep(DEFAULT_SLEEP)

        self.cli.node.update.assert_called_with(self.uuid, mock.ANY)
        self.assertCalledWithPatch(self.patch, self.cli.node.update)
        self.assertFalse(self.cli.port.create.called)
        self.assertFalse(self.cli.node.set_boot_device.called)

        status = self.call_get_status(self.uuid)
        self.check_status(status, finished=True, state=istate.States.finished)

    def test_update_known_active_node(self):
        # Start with a normal introspection as a pre-requisite
        self.test_bmc()

        self.cli.node.update.reset_mock()
        self.cli.node.set_boot_device.reset_mock()
        self.cli.port.create.reset_mock()
        # Provide some updates
        self.data['inventory']['memory']['physical_mb'] = 16384
        self.patch = [
            {'op': 'add', 'path': '/properties/cpus', 'value': '4'},
            {'path': '/properties/cpu_arch', 'value': 'x86_64', 'op': 'add'},
            {'op': 'add', 'path': '/properties/memory_mb', 'value': '16384'},
            {'path': '/properties/local_gb', 'value': '999', 'op': 'add'}
        ]

        # Then continue with active node test
        self.test_update_unknown_active_node()


@contextlib.contextmanager
def mocked_server():
    conf_file = get_test_conf_file()
    dbsync.main(args=['--config-file', conf_file, 'upgrade'])

    cfg.CONF.reset()
    cfg.CONF.unregister_opt(dbsync.command_opt)

    eventlet.greenthread.spawn_n(inspector_cmd.main,
                                 args=['--config-file', conf_file])
    eventlet.greenthread.sleep(1)
    # Wait for service to start up to 30 seconds
    for i in range(10):
        try:
            requests.get('http://127.0.0.1:5050/v1')
        except requests.ConnectionError:
            if i == 9:
                raise
            print('Service did not start yet')
            eventlet.greenthread.sleep(3)
        else:
            break
    # start testing
    yield
    # Make sure all processes finished executing
    eventlet.greenthread.sleep(1)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
    else:
        test_name = None

    with mocked_server():
        unittest.main(verbosity=2, defaultTest=test_name)
