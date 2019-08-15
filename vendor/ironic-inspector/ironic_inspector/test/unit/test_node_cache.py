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

import copy
import datetime
import json
import unittest

import automaton
import mock
from oslo_config import cfg
import oslo_db
from oslo_utils import timeutils
from oslo_utils import uuidutils
import six

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector.common import locking
from ironic_inspector import db
from ironic_inspector import introspection_state as istate
from ironic_inspector import node_cache
from ironic_inspector.test import base as test_base
from ironic_inspector import utils

CONF = cfg.CONF


class TestNodeCache(test_base.NodeTest):
    def test_add_node(self):
        # Ensure previous node information is cleared
        uuid2 = uuidutils.generate_uuid()
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.node.uuid,
                    state=istate.States.starting).save(session)
            db.Node(uuid=uuid2,
                    state=istate.States.starting).save(session)
            db.Attribute(uuid=uuidutils.generate_uuid(), name='mac',
                         value='11:22:11:22:11:22',
                         node_uuid=self.uuid).save(session)

        node = node_cache.add_node(self.node.uuid,
                                   istate.States.starting,
                                   mac=self.macs, bmc_address='1.2.3.4',
                                   foo=None)
        self.assertEqual(self.uuid, node.uuid)
        self.assertTrue(
            (datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
                < node.started_at <
             datetime.datetime.utcnow() + datetime.timedelta(seconds=60)))
        self.assertFalse(node._lock.is_locked())

        res = set(db.model_query(db.Node.uuid,
                                 db.Node.started_at).all())

        expected = {(node.uuid, node.started_at), (uuid2, None)}
        self.assertEqual(expected, res)

        res = db.model_query(db.Node).get(self.uuid)
        self.assertIsNotNone(res.version_id)

        res = (db.model_query(db.Attribute.name,
                              db.Attribute.value, db.Attribute.node_uuid).
               order_by(db.Attribute.name, db.Attribute.value).all())
        self.assertEqual([('bmc_address', '1.2.3.4', self.uuid),
                          ('mac', self.macs[0], self.uuid),
                          ('mac', self.macs[1], self.uuid),
                          ('mac', self.macs[2], self.uuid)],
                         [(row.name, row.value, row.node_uuid) for row in res])

    def test__delete_node(self):
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.node.uuid,
                    state=istate.States.finished).save(session)
            db.Attribute(uuid=uuidutils.generate_uuid(), name='mac',
                         value='11:22:11:22:11:22', node_uuid=self.uuid).save(
                             session)
            data = {'s': 'value', 'b': True, 'i': 42}
            encoded = json.dumps(data)
            db.Option(uuid=self.uuid, name='name', value=encoded).save(
                session)

        node_cache._delete_node(self.uuid)
        session = db.get_writer_session()
        row_node = db.model_query(db.Node).filter_by(
            uuid=self.uuid).first()
        self.assertIsNone(row_node)
        row_attribute = db.model_query(db.Attribute).filter_by(
            node_uuid=self.uuid).first()
        self.assertIsNone(row_attribute)
        row_option = db.model_query(db.Option).filter_by(
            uuid=self.uuid).first()
        self.assertIsNone(row_option)

    @mock.patch.object(locking, 'get_lock', autospec=True)
    @mock.patch.object(node_cache, '_list_node_uuids')
    @mock.patch.object(node_cache, '_delete_node')
    def test_delete_nodes_not_in_list(self, mock__delete_node,
                                      mock__list_node_uuids,
                                      mock_get_lock):
        uuid2 = uuidutils.generate_uuid()
        uuids = {self.uuid}
        mock__list_node_uuids.return_value = {self.uuid, uuid2}
        session = db.get_writer_session()
        with session.begin():
            node_cache.delete_nodes_not_in_list(uuids)
        mock__delete_node.assert_called_once_with(uuid2)
        mock_get_lock.assert_called_once_with(uuid2)
        mock_get_lock.return_value.__enter__.assert_called_once_with()

    def test_active_macs(self):
        session = db.get_writer_session()
        uuid2 = uuidutils.generate_uuid()
        with session.begin():
            db.Node(uuid=self.node.uuid,
                    state=istate.States.starting).save(session)
            db.Node(uuid=uuid2,
                    state=istate.States.starting,
                    manage_boot=False).save(session)
            values = [('mac', '11:22:11:22:11:22', self.uuid),
                      ('mac', '22:11:22:11:22:11', self.uuid),
                      ('mac', 'aa:bb:cc:dd:ee:ff', uuid2)]
            for value in values:
                db.Attribute(uuid=uuidutils.generate_uuid(), name=value[0],
                             value=value[1], node_uuid=value[2]).save(session)
        self.assertEqual({'11:22:11:22:11:22', '22:11:22:11:22:11',
                          # We still need to serve DHCP to unmanaged nodes
                          'aa:bb:cc:dd:ee:ff'},
                         node_cache.active_macs())

    def test__list_node_uuids(self):
        session = db.get_writer_session()
        uuid2 = uuidutils.generate_uuid()
        with session.begin():
            db.Node(uuid=self.node.uuid,
                    state=istate.States.starting).save(session)
            db.Node(uuid=uuid2,
                    state=istate.States.starting).save(session)

        node_uuid_list = node_cache._list_node_uuids()
        self.assertEqual({self.uuid, uuid2}, node_uuid_list)

    def test_add_attribute(self):
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.node.uuid,
                    state=istate.States.starting).save(session)
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=42)
        node_info.add_attribute('key', 'value')
        res = db.model_query(db.Attribute.name,
                             db.Attribute.value,
                             db.Attribute.node_uuid,
                             session=session)
        res = res.order_by(db.Attribute.name, db.Attribute.value).all()
        self.assertEqual([('key', 'value', self.uuid)],
                         [tuple(row) for row in res])
        # check that .attributes got invalidated and reloaded
        self.assertEqual({'key': ['value']}, node_info.attributes)

    def test_add_attribute_same_name(self):
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.node.uuid,
                    state=istate.States.starting).save(session)
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=42)

        node_info.add_attribute('key', ['foo', 'bar'])
        node_info.add_attribute('key', 'baz')
        res = db.model_query(db.Attribute.name, db.Attribute.value,
                             db.Attribute.node_uuid, session=session)
        res = res.order_by(db.Attribute.name, db.Attribute.value).all()
        self.assertEqual([('key', 'bar', self.uuid),
                          ('key', 'baz', self.uuid),
                          ('key', 'foo', self.uuid)],
                         [tuple(row) for row in res])

    def test_add_attribute_same_value(self):
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.node.uuid,
                    state=istate.States.starting).save(session)
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=42)

        node_info.add_attribute('key', 'value')
        node_info.add_attribute('key', 'value')
        res = db.model_query(db.Attribute.name, db.Attribute.value,
                             db.Attribute.node_uuid, session=session)
        self.assertEqual([('key', 'value', self.uuid),
                          ('key', 'value', self.uuid)],
                         [tuple(row) for row in res])

    def test_attributes(self):
        node_info = node_cache.add_node(self.uuid,
                                        istate.States.starting,
                                        bmc_address='1.2.3.4',
                                        mac=self.macs)
        self.assertEqual({'bmc_address': ['1.2.3.4'],
                          'mac': self.macs},
                         node_info.attributes)
        # check invalidation
        session = db.get_writer_session()
        with session.begin():
            db.Attribute(uuid=uuidutils.generate_uuid(), name='foo',
                         value='bar', node_uuid=self.uuid).save(session)
        # still cached
        self.assertEqual({'bmc_address': ['1.2.3.4'],
                          'mac': self.macs},
                         node_info.attributes)
        node_info.invalidate_cache()
        self.assertEqual({'bmc_address': ['1.2.3.4'],
                          'mac': self.macs, 'foo': ['bar']},
                         node_info.attributes)


class TestNodeCacheFind(test_base.NodeTest):
    def setUp(self):
        super(TestNodeCacheFind, self).setUp()
        self.macs2 = ['00:00:00:00:00:00']
        node_cache.add_node(self.uuid,
                            istate.States.starting,
                            bmc_address='1.2.3.4',
                            mac=self.macs)

    def test_no_data(self):
        self.assertRaises(utils.Error, node_cache.find_node)
        self.assertRaises(utils.Error, node_cache.find_node, mac=[])

    def test_bmc(self):
        res = node_cache.find_node(bmc_address='1.2.3.4')
        self.addCleanup(res.release_lock)
        self.assertEqual(self.uuid, res.uuid)
        self.assertTrue(
            datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
            < res.started_at <
            datetime.datetime.utcnow() + datetime.timedelta(seconds=1))
        self.assertTrue(res._lock.is_locked())

    def test_same_bmc_different_macs(self):
        uuid2 = uuidutils.generate_uuid()
        node_cache.add_node(uuid2,
                            istate.States.starting,
                            bmc_address='1.2.3.4',
                            mac=self.macs2)
        res = node_cache.find_node(bmc_address='1.2.3.4', mac=self.macs)
        self.addCleanup(res.release_lock)
        self.assertEqual(self.uuid, res.uuid)
        res = node_cache.find_node(bmc_address='1.2.3.4', mac=self.macs2)
        self.addCleanup(res.release_lock)
        self.assertEqual(uuid2, res.uuid)

    def test_same_bmc_raises(self):
        uuid2 = uuidutils.generate_uuid()
        node_cache.add_node(uuid2,
                            istate.States.starting,
                            bmc_address='1.2.3.4')
        six.assertRaisesRegex(self, utils.Error, 'Multiple nodes',
                              node_cache.find_node, bmc_address='1.2.3.4')

    def test_macs(self):
        res = node_cache.find_node(mac=['11:22:33:33:33:33', self.macs[1]])
        self.addCleanup(res.release_lock)
        self.assertEqual(self.uuid, res.uuid)
        self.assertTrue(
            datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
            < res.started_at <
            datetime.datetime.utcnow() + datetime.timedelta(seconds=1))
        self.assertTrue(res._lock.is_locked())

    def test_macs_not_found(self):
        self.assertRaises(utils.Error, node_cache.find_node,
                          mac=['11:22:33:33:33:33',
                               '66:66:44:33:22:11'])

    def test_macs_multiple_found(self):
        node_cache.add_node('uuid2',
                            istate.States.starting,
                            mac=self.macs2)
        self.assertRaises(utils.Error, node_cache.find_node,
                          mac=[self.macs[0], self.macs2[0]])

    def test_both(self):
        res = node_cache.find_node(bmc_address='1.2.3.4',
                                   mac=self.macs)
        self.addCleanup(res.release_lock)
        self.assertEqual(self.uuid, res.uuid)
        self.assertTrue(
            datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
            < res.started_at <
            datetime.datetime.utcnow() + datetime.timedelta(seconds=1))
        self.assertTrue(res._lock.is_locked())

    def test_inconsistency(self):
        session = db.get_writer_session()
        with session.begin():
            (db.model_query(db.Node).filter_by(uuid=self.uuid).
                delete())
        self.assertRaises(utils.Error, node_cache.find_node,
                          bmc_address='1.2.3.4')

    def test_already_finished(self):
        session = db.get_writer_session()
        with session.begin():
            (db.model_query(db.Node).filter_by(uuid=self.uuid).
                update({'finished_at': datetime.datetime.utcnow()}))
        self.assertRaises(utils.Error, node_cache.find_node,
                          bmc_address='1.2.3.4')

    def test_input_filtering(self):
        self.assertRaises(utils.NotFoundInCacheError,
                          node_cache.find_node,
                          bmc_address="' OR ''='")


class TestNodeCacheCleanUp(test_base.NodeTest):
    def setUp(self):
        super(TestNodeCacheCleanUp, self).setUp()
        self.started_at = datetime.datetime.utcnow()
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.uuid,
                    state=istate.States.waiting,
                    started_at=self.started_at).save(
                session)
            for v in self.macs:
                db.Attribute(uuid=uuidutils.generate_uuid(), name='mac',
                             value=v, node_uuid=self.uuid).save(session)
            db.Option(uuid=self.uuid, name='foo', value='bar').save(
                session)
            db.IntrospectionData(uuid=self.uuid, processed=False,
                                 data={'fake': 'data'}).save(session)

    def test_no_timeout(self):
        CONF.set_override('timeout', 0)

        self.assertFalse(node_cache.clean_up())

        res = [tuple(row) for row in
               db.model_query(db.Node.finished_at,
                              db.Node.error).all()]
        self.assertEqual([(None, None)], res)
        self.assertEqual(len(self.macs),
                         db.model_query(db.Attribute).count())
        self.assertEqual(1, db.model_query(db.Option).count())

    @mock.patch.object(locking, 'get_lock', autospec=True)
    @mock.patch.object(timeutils, 'utcnow')
    def test_ok(self, time_mock, get_lock_mock):
        time_mock.return_value = datetime.datetime.utcnow()

        self.assertFalse(node_cache.clean_up())

        res = [tuple(row) for row in db.model_query(
            db.Node.finished_at, db.Node.error).all()]
        self.assertEqual([(None, None)], res)
        self.assertEqual(len(self.macs),
                         db.model_query(db.Attribute).count())
        self.assertEqual(1, db.model_query(db.Option).count())
        self.assertEqual(1, db.model_query(db.IntrospectionData).count())
        self.assertFalse(get_lock_mock.called)

    @mock.patch.object(node_cache.NodeInfo, 'acquire_lock', autospec=True)
    @mock.patch.object(timeutils, 'utcnow')
    def test_timeout(self, time_mock, lock_mock):
        # Add a finished node to confirm we don't try to timeout it
        time_mock.return_value = self.started_at
        session = db.get_writer_session()
        finished_at = self.started_at + datetime.timedelta(seconds=60)
        with session.begin():
            db.Node(uuid=self.uuid + '1', started_at=self.started_at,
                    state=istate.States.waiting,
                    finished_at=finished_at).save(session)
        CONF.set_override('timeout', 99)
        time_mock.return_value = (self.started_at +
                                  datetime.timedelta(seconds=100))

        self.assertEqual([self.uuid], node_cache.clean_up())

        res = [(row.state, row.finished_at, row.error) for row in
               db.model_query(db.Node).all()]
        self.assertEqual(
            [(istate.States.error,
              self.started_at + datetime.timedelta(seconds=100),
              'Introspection timeout'),
             (istate.States.waiting,
              self.started_at + datetime.timedelta(seconds=60), None)],
            res)
        self.assertEqual([], db.model_query(db.Attribute).all())
        self.assertEqual([], db.model_query(db.Option).all())
        lock_mock.assert_called_once_with(mock.ANY, blocking=False)

    @mock.patch.object(locking, 'get_lock', autospec=True)
    @mock.patch.object(timeutils, 'utcnow')
    def test_timeout_active_state(self, time_mock, lock_mock):
        time_mock.return_value = self.started_at
        session = db.get_writer_session()
        CONF.set_override('timeout', 1)
        for state in [istate.States.starting, istate.States.enrolling,
                      istate.States.processing, istate.States.reapplying]:
            db.model_query(db.Node, session=session).filter_by(
                uuid=self.uuid).update({'state': state, 'finished_at': None})

            current_time = self.started_at + datetime.timedelta(seconds=2)
            time_mock.return_value = current_time

            self.assertEqual([self.uuid], node_cache.clean_up())

            res = [(row.state, row.finished_at, row.error) for row in
                   db.model_query(db.Node).all()]
            self.assertEqual(
                [(istate.States.error, current_time, 'Introspection timeout')],
                res)

    @mock.patch.object(node_cache.NodeInfo, 'acquire_lock', autospec=True)
    @mock.patch.object(timeutils, 'utcnow')
    def test_timeout_lock_failed(self, time_mock, get_lock_mock):
        time_mock.return_value = self.started_at
        CONF.set_override('timeout', 1)
        get_lock_mock.return_value = False
        current_time = self.started_at + datetime.timedelta(seconds=2)
        time_mock.return_value = current_time

        self.assertEqual([], node_cache.clean_up())

        res = [(row.state, row.finished_at, row.error) for row in
               db.model_query(db.Node).all()]
        self.assertEqual([('waiting', None, None)], res)
        get_lock_mock.assert_called_once_with(mock.ANY, blocking=False)


class TestNodeCacheGetNode(test_base.NodeTest):
    def test_ok(self):
        started_at = (datetime.datetime.utcnow() -
                      datetime.timedelta(seconds=42))
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.uuid,
                    state=istate.States.starting,
                    started_at=started_at).save(session)
        info = node_cache.get_node(self.uuid)

        self.assertEqual(self.uuid, info.uuid)
        self.assertEqual(started_at, info.started_at)
        self.assertIsNone(info.finished_at)
        self.assertIsNone(info.error)
        self.assertFalse(info._lock.is_locked())

    def test_not_found(self):
        self.assertRaises(utils.Error, node_cache.get_node,
                          uuidutils.generate_uuid())

    def test_with_name(self):
        started_at = (datetime.datetime.utcnow() -
                      datetime.timedelta(seconds=42))
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.uuid,
                    state=istate.States.starting,
                    started_at=started_at).save(session)
        ironic = mock.Mock()
        ironic.node.get.return_value = self.node

        info = node_cache.get_node('name', ironic=ironic)

        self.assertEqual(self.uuid, info.uuid)
        self.assertEqual(started_at, info.started_at)
        self.assertIsNone(info.finished_at)
        self.assertIsNone(info.error)
        self.assertFalse(info._lock.is_locked())
        ironic.node.get.assert_called_once_with('name')


@mock.patch.object(timeutils, 'utcnow', lambda: datetime.datetime(1, 1, 1))
class TestNodeInfoFinished(test_base.NodeTest):
    def setUp(self):
        super(TestNodeInfoFinished, self).setUp()
        node_cache.add_node(self.uuid,
                            istate.States.processing,
                            bmc_address='1.2.3.4',
                            mac=self.macs)
        self.node_info = node_cache.NodeInfo(
            uuid=self.uuid, started_at=datetime.datetime(3, 1, 4))
        session = db.get_writer_session()
        with session.begin():
            db.Option(uuid=self.uuid, name='foo', value='bar').save(
                session)

    def test_success(self):
        self.node_info.finished(istate.Events.finish)

        session = db.get_writer_session()
        with session.begin():
            self.assertEqual((datetime.datetime(1, 1, 1), None),
                             tuple(db.model_query(
                                   db.Node.finished_at,
                                   db.Node.error).first()))
            self.assertEqual([], db.model_query(db.Attribute,
                             session=session).all())
            self.assertEqual([], db.model_query(db.Option,
                             session=session).all())

    def test_error(self):
        self.node_info.finished(istate.Events.error, error='boom')

        self.assertEqual((datetime.datetime(1, 1, 1), 'boom'),
                         tuple(db.model_query(db.Node.finished_at,
                               db.Node.error).first()))
        self.assertEqual([], db.model_query(db.Attribute).all())
        self.assertEqual([], db.model_query(db.Option).all())

    def test_release_lock(self):
        self.node_info.acquire_lock()
        self.node_info.finished(istate.Events.finish)
        self.assertFalse(self.node_info._lock.is_locked())


class TestNodeInfoOptions(test_base.NodeTest):
    def setUp(self):
        super(TestNodeInfoOptions, self).setUp()
        node_cache.add_node(self.uuid,
                            istate.States.starting,
                            bmc_address='1.2.3.4',
                            mac=self.macs)
        self.node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=3.14)
        session = db.get_writer_session()
        with session.begin():
            db.Option(uuid=self.uuid, name='foo', value='"bar"').save(
                session)

    def test_get(self):
        self.assertEqual({'foo': 'bar'}, self.node_info.options)
        # should be cached
        self.assertEqual(self.node_info.options, self.node_info.options)
        # invalidate cache
        old_options = self.node_info.options
        self.node_info.invalidate_cache()
        self.assertIsNot(old_options, self.node_info.options)
        self.assertEqual(old_options, self.node_info.options)

    def test_set(self):
        data = {'s': 'value', 'b': True, 'i': 42}
        self.node_info.set_option('name', data)
        self.assertEqual(data, self.node_info.options['name'])

        new = node_cache.NodeInfo(uuid=self.uuid, started_at=3.14)
        self.assertEqual(data, new.options['name'])


@mock.patch.object(ir_utils, 'get_client', autospec=True)
class TestNodeCacheIronicObjects(unittest.TestCase):
    def setUp(self):
        super(TestNodeCacheIronicObjects, self).setUp()
        self.ports = {'mac1': mock.Mock(address='mac1', spec=['address']),
                      'mac2': mock.Mock(address='mac2', spec=['address'])}
        self.uuid = uuidutils.generate_uuid()

    def test_node_provided(self, mock_ironic):
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                        node=mock.sentinel.node)
        self.assertIs(mock.sentinel.node, node_info.node())
        self.assertFalse(mock_ironic.called)

    def test_node_not_provided(self, mock_ironic):
        mock_ironic.return_value.node.get.return_value = mock.sentinel.node
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0)

        self.assertIs(mock.sentinel.node, node_info.node())
        self.assertIs(node_info.node(), node_info.node())

        mock_ironic.assert_called_once_with()
        mock_ironic.return_value.node.get.assert_called_once_with(self.uuid)

    def test_node_ironic_preset(self, mock_ironic):
        mock_ironic2 = mock.Mock()
        mock_ironic2.node.get.return_value = mock.sentinel.node
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                        ironic=mock_ironic2)
        self.assertIs(mock.sentinel.node, node_info.node())

        self.assertFalse(mock_ironic.called)
        mock_ironic2.node.get.assert_called_once_with(self.uuid)

    def test_ports_provided(self, mock_ironic):
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                        ports=self.ports)
        self.assertIs(self.ports, node_info.ports())
        self.assertFalse(mock_ironic.called)

    def test_ports_provided_list(self, mock_ironic):
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                        ports=list(self.ports.values()))
        self.assertEqual(self.ports, node_info.ports())
        self.assertFalse(mock_ironic.called)

    def test_ports_not_provided(self, mock_ironic):
        mock_ironic.return_value.node.list_ports.return_value = list(
            self.ports.values())
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0)

        self.assertEqual(self.ports, node_info.ports())
        self.assertIs(node_info.ports(), node_info.ports())

        mock_ironic.assert_called_once_with()
        mock_ironic.return_value.node.list_ports.assert_called_once_with(
            self.uuid, limit=0, detail=True)

    def test_ports_ironic_preset(self, mock_ironic):
        mock_ironic2 = mock.Mock()
        mock_ironic2.node.list_ports.return_value = list(
            self.ports.values())
        node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                        ironic=mock_ironic2)
        self.assertEqual(self.ports, node_info.ports())

        self.assertFalse(mock_ironic.called)
        mock_ironic2.node.list_ports.assert_called_once_with(
            self.uuid, limit=0, detail=True)


class TestUpdate(test_base.NodeTest):
    def setUp(self):
        super(TestUpdate, self).setUp()
        self.ironic = mock.Mock()
        self.ports = {'mac%d' % i: mock.Mock(address='mac%d' % i, uuid=str(i))
                      for i in range(2)}
        self.node_info = node_cache.NodeInfo(uuid=self.uuid,
                                             started_at=0,
                                             node=self.node,
                                             ports=self.ports,
                                             ironic=self.ironic)

    def test_patch(self):
        self.ironic.node.update.return_value = mock.sentinel.node

        self.node_info.patch([{'patch': 'patch'}])

        self.ironic.node.update.assert_called_once_with(self.uuid,
                                                        [{'patch': 'patch'}])
        self.assertIs(mock.sentinel.node, self.node_info.node())

    def test_patch_path_wo_leading_slash(self):
        self.ironic.node.update.return_value = mock.sentinel.node

        patch = [{'op': 'add', 'path': 'driver_info/test', 'value': 42}]
        expected_patch = copy.deepcopy(patch)
        expected_patch[0]['path'] = '/' + 'driver_info/test'

        self.node_info.patch(patch)

        self.ironic.node.update.assert_called_once_with(self.uuid,
                                                        expected_patch)
        self.assertIs(mock.sentinel.node, self.node_info.node())

    def test_patch_path_with_leading_slash(self):
        self.ironic.node.update.return_value = mock.sentinel.node

        patch = [{'op': 'add', 'path': '/driver_info/test', 'value': 42}]

        self.node_info.patch(patch)

        self.ironic.node.update.assert_called_once_with(self.uuid, patch)
        self.assertIs(mock.sentinel.node, self.node_info.node())

    def test_patch_with_args(self):
        self.ironic.node.update.return_value = mock.sentinel.node

        self.node_info.patch([{'patch': 'patch'}], reset_interfaces=True)

        self.ironic.node.update.assert_called_once_with(self.uuid,
                                                        [{'patch': 'patch'}],
                                                        reset_interfaces=True)
        self.assertIs(mock.sentinel.node, self.node_info.node())

    def test_update_properties(self):
        self.ironic.node.update.return_value = mock.sentinel.node

        self.node_info.update_properties(prop=42)

        patch = [{'op': 'add', 'path': '/properties/prop', 'value': 42}]
        self.ironic.node.update.assert_called_once_with(self.uuid, patch)
        self.assertIs(mock.sentinel.node, self.node_info.node())

    def test_update_capabilities(self):
        self.ironic.node.update.return_value = mock.sentinel.node
        self.node.properties['capabilities'] = 'foo:bar,x:y'

        self.node_info.update_capabilities(x=1, y=2)

        self.ironic.node.update.assert_called_once_with(self.uuid, mock.ANY)
        patch = self.ironic.node.update.call_args[0][1]
        new_caps = ir_utils.capabilities_to_dict(patch[0]['value'])
        self.assertEqual({'foo': 'bar', 'x': '1', 'y': '2'}, new_caps)

    def test_replace_field(self):
        self.ironic.node.update.return_value = mock.sentinel.node
        self.node.extra['foo'] = 'bar'

        self.node_info.replace_field('/extra/foo', lambda v: v + '1')

        patch = [{'op': 'replace', 'path': '/extra/foo', 'value': 'bar1'}]
        self.ironic.node.update.assert_called_once_with(self.uuid, patch)
        self.assertIs(mock.sentinel.node, self.node_info.node())

    def test_replace_field_not_found(self):
        self.ironic.node.update.return_value = mock.sentinel.node

        self.assertRaises(KeyError, self.node_info.replace_field,
                          '/extra/foo', lambda v: v + '1')

    def test_replace_field_with_default(self):
        self.ironic.node.update.return_value = mock.sentinel.node

        self.node_info.replace_field('/extra/foo', lambda v: v + [42],
                                     default=[])

        patch = [{'op': 'add', 'path': '/extra/foo', 'value': [42]}]
        self.ironic.node.update.assert_called_once_with(self.uuid, patch)
        self.assertIs(mock.sentinel.node, self.node_info.node())

    def test_replace_field_same_value(self):
        self.ironic.node.update.return_value = mock.sentinel.node
        self.node.extra['foo'] = 'bar'

        self.node_info.replace_field('/extra/foo', lambda v: v)
        self.assertFalse(self.ironic.node.update.called)

    def test_patch_port(self):
        self.ironic.port.update.return_value = mock.sentinel.port

        self.node_info.patch_port(self.ports['mac0'], ['patch'])

        self.ironic.port.update.assert_called_once_with('0', ['patch'])
        self.assertIs(mock.sentinel.port,
                      self.node_info.ports()['mac0'])

    def test_patch_port_by_mac(self):
        self.ironic.port.update.return_value = mock.sentinel.port

        self.node_info.patch_port('mac0', ['patch'])

        self.ironic.port.update.assert_called_once_with('0', ['patch'])
        self.assertIs(mock.sentinel.port,
                      self.node_info.ports()['mac0'])

    def test_delete_port(self):
        self.node_info.delete_port(self.ports['mac0'])

        self.ironic.port.delete.assert_called_once_with('0')
        self.assertEqual(['mac1'], list(self.node_info.ports()))

    def test_delete_port_by_mac(self):
        self.node_info.delete_port('mac0')

        self.ironic.port.delete.assert_called_once_with('0')
        self.assertEqual(['mac1'], list(self.node_info.ports()))

    @mock.patch.object(node_cache.LOG, 'warning', autospec=True)
    def test_create_ports(self, mock_warn):
        ports = [
            'mac2',
            {'mac': 'mac3', 'client_id': '42', 'pxe': False},
            {'mac': 'mac4', 'pxe': True}
        ]

        self.node_info.create_ports(ports)
        self.assertEqual({'mac0', 'mac1', 'mac2', 'mac3', 'mac4'},
                         set(self.node_info.ports()))

        create_calls = [
            mock.call(node_uuid=self.uuid, address='mac2', extra={},
                      pxe_enabled=True),
            mock.call(node_uuid=self.uuid, address='mac3',
                      extra={'client-id': '42'}, pxe_enabled=False),
            mock.call(node_uuid=self.uuid, address='mac4', extra={},
                      pxe_enabled=True),
        ]
        self.assertEqual(create_calls, self.ironic.port.create.call_args_list)
        # No conflicts - cache was not cleared - no calls to port.list
        self.assertFalse(mock_warn.called)
        self.assertFalse(self.ironic.port.list.called)

    @mock.patch.object(node_cache.LOG, 'info', autospec=True)
    def test__create_port(self, mock_info):
        uuid = uuidutils.generate_uuid()
        address = 'mac1'
        self.ironic.port.create.return_value = mock.Mock(uuid=uuid,
                                                         address=address)

        self.node_info._create_port(address, client_id='42')

        self.ironic.port.create.assert_called_once_with(
            node_uuid=self.uuid, address='mac1', client_id='42')
        mock_info.assert_called_once_with(
            mock.ANY, {'uuid': uuid, 'mac': address,
                       'attrs': {'client_id': '42'}},
            node_info=self.node_info)

    @mock.patch.object(node_cache.LOG, 'warning', autospec=True)
    def test_create_ports_with_conflicts(self, mock_warn):
        self.ironic.port.create.return_value = mock.Mock(
            uuid='fake', address='mac')

        ports = [
            'mac',
            {'mac': 'mac0'},
            'mac1',
            {'mac': 'mac2', 'client_id': '42', 'pxe': False},
        ]

        self.node_info.create_ports(ports)

        create_calls = [
            mock.call(node_uuid=self.uuid, address='mac', extra={},
                      pxe_enabled=True),
            mock.call(node_uuid=self.uuid, address='mac2',
                      extra={'client-id': '42'}, pxe_enabled=False),
        ]
        self.assertEqual(create_calls, self.ironic.port.create.call_args_list)
        mock_warn.assert_called_once_with(mock.ANY, ['mac0', 'mac1'],
                                          node_info=self.node_info)


class TestNodeCacheGetByPath(test_base.NodeTest):
    def setUp(self):
        super(TestNodeCacheGetByPath, self).setUp()
        self.node = mock.Mock(spec=['uuid', 'properties'],
                              properties={'answer': 42},
                              uuid=self.uuid)
        self.node_info = node_cache.NodeInfo(uuid=self.uuid, started_at=0,
                                             node=self.node)

    def test_get_by_path(self):
        self.assertEqual(self.uuid, self.node_info.get_by_path('/uuid'))
        self.assertEqual(self.uuid, self.node_info.get_by_path('uuid'))
        self.assertEqual(42, self.node_info.get_by_path('/properties/answer'))
        self.assertRaises(KeyError, self.node_info.get_by_path, '/foo')
        self.assertRaises(KeyError, self.node_info.get_by_path, '/extra/foo')


@mock.patch.object(locking.lockutils, 'internal_lock', autospec=True)
class TestInternalLock(test_base.NodeTest):
    def test_acquire(self, lock_mock):
        node_info = node_cache.NodeInfo(self.uuid)
        self.addCleanup(node_info.release_lock)
        self.assertFalse(node_info._lock.is_locked())
        lock_mock.assert_called_once_with('node-{}'.format(self.uuid),
                                          semaphores=mock.ANY)
        self.assertFalse(lock_mock.return_value.acquire.called)

        self.assertTrue(node_info.acquire_lock())
        self.assertTrue(node_info._lock.is_locked())
        self.assertTrue(node_info.acquire_lock())
        self.assertTrue(node_info._lock.is_locked())
        lock_mock.return_value.acquire.assert_called_once_with(blocking=True)

    def test_release(self, lock_mock):
        node_info = node_cache.NodeInfo(self.uuid)
        node_info.acquire_lock()
        self.assertTrue(node_info._lock.is_locked())
        node_info.release_lock()
        self.assertFalse(node_info._lock.is_locked())
        node_info.release_lock()
        self.assertFalse(node_info._lock.is_locked())
        lock_mock.return_value.acquire.assert_called_once_with(blocking=True)
        lock_mock.return_value.release.assert_called_once_with()

    def test_acquire_non_blocking(self, lock_mock):
        node_info = node_cache.NodeInfo(self.uuid)
        self.addCleanup(node_info.release_lock)
        self.assertFalse(node_info._lock.is_locked())
        lock_mock.return_value.acquire.side_effect = iter([False, True])

        self.assertFalse(node_info.acquire_lock(blocking=False))
        self.assertFalse(node_info._lock.is_locked())
        self.assertTrue(node_info.acquire_lock(blocking=False))
        self.assertTrue(node_info._lock.is_locked())
        self.assertTrue(node_info.acquire_lock(blocking=False))
        self.assertTrue(node_info._lock.is_locked())
        lock_mock.return_value.acquire.assert_called_with(blocking=False)
        self.assertEqual(2, lock_mock.return_value.acquire.call_count)


@mock.patch.object(node_cache, 'add_node', autospec=True)
@mock.patch.object(ir_utils, 'get_client', autospec=True)
class TestNodeCreate(test_base.NodeTest):
    def setUp(self):
        super(TestNodeCreate, self).setUp()
        self.mock_client = mock.Mock()

    def test_default_create(self, mock_get_client, mock_add_node):
        mock_get_client.return_value = self.mock_client
        self.mock_client.node.create.return_value = self.node

        node_cache.create_node('fake')

        self.mock_client.node.create.assert_called_once_with(driver='fake')
        mock_add_node.assert_called_once_with(
            self.node.uuid,
            istate.States.enrolling,
            ironic=self.mock_client)

    def test_create_with_args(self, mock_get_client, mock_add_node):
        mock_get_client.return_value = self.mock_client
        self.mock_client.node.create.return_value = self.node

        node_cache.create_node('agent_ipmitool', ironic=self.mock_client)

        self.assertFalse(mock_get_client.called)
        self.mock_client.node.create.assert_called_once_with(
            driver='agent_ipmitool')
        mock_add_node.assert_called_once_with(
            self.node.uuid,
            istate.States.enrolling,
            ironic=self.mock_client)

    def test_create_client_error(self, mock_get_client, mock_add_node):
        mock_get_client.return_value = self.mock_client
        self.mock_client.node.create.side_effect = (
            node_cache.exceptions.InvalidAttribute)

        node_cache.create_node('fake')

        mock_get_client.assert_called_once_with()
        self.mock_client.node.create.assert_called_once_with(driver='fake')
        self.assertFalse(mock_add_node.called)


class TestNodeCacheListNode(test_base.NodeTest):
    def setUp(self):
        super(TestNodeCacheListNode, self).setUp()
        self.uuid2 = uuidutils.generate_uuid()
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.uuid,
                    started_at=datetime.datetime(1, 1, 2)).save(session)
            db.Node(uuid=self.uuid2, started_at=datetime.datetime(1, 1, 1),
                    finished_at=datetime.datetime(1, 1, 3)).save(session)

    # mind please node(self.uuid).started_at > node(self.uuid2).started_at
    # and the result ordering is strict in node_cache.get_node_list newer first

    def test_list_node(self):
        nodes = node_cache.get_node_list()

        self.assertEqual([self.uuid, self.uuid2],
                         [node.uuid for node in nodes])

    def test_list_node_limit(self):
        nodes = node_cache.get_node_list(limit=1)
        self.assertEqual([self.uuid], [node.uuid for node in nodes])

    def test_list_node_marker(self):
        # get nodes started_at after node(self.uuid)
        nodes = node_cache.get_node_list(marker=self.uuid)
        self.assertEqual([self.uuid2], [node.uuid for node in nodes])

    def test_list_node_wrong_marker(self):
        self.assertRaises(utils.Error, node_cache.get_node_list,
                          marker='foo-bar')


class TestNodeInfoVersionId(test_base.NodeStateTest):
    def test_get(self):
        self.node_info._version_id = None
        self.assertEqual(self.db_node.version_id, self.node_info.version_id)

    def test_get_missing_uuid(self):
        self.node_info.uuid = 'foo'
        self.node_info._version_id = None

        def func():
            return self.node_info.version_id

        six.assertRaisesRegex(self, utils.NotFoundInCacheError, '.*', func)

    def test_set(self):
        with db.ensure_transaction() as session:
            self.node_info._set_version_id(uuidutils.generate_uuid(),
                                           session)
        row = db.model_query(db.Node).get(self.node_info.uuid)
        self.assertEqual(self.node_info.version_id, row.version_id)

    def test_set_race(self):
        with db.ensure_transaction() as session:
            row = db.model_query(db.Node, session=session).get(
                self.node_info.uuid)
            row.update({'version_id': uuidutils.generate_uuid()})
            row.save(session)

        six.assertRaisesRegex(self, utils.NodeStateRaceCondition,
                              'Node state mismatch', self.node_info._set_state,
                              istate.States.finished)


class TestNodeInfoState(test_base.NodeStateTest):
    def test_get(self):
        self.node_info._state = None
        self.assertEqual(self.db_node.state, self.node_info.state)

    def test_set(self):
        self.node_info._set_state(istate.States.finished)
        row = db.model_query(db.Node).get(self.node_info.uuid)
        self.assertEqual(self.node_info.state, row.state)

    def test_set_invalid_state(self):
        six.assertRaisesRegex(self, oslo_db.exception.DBError,
                              'constraint failed',
                              self.node_info._set_state, 'foo')

    def test_commit(self):
        current_time = timeutils.utcnow()
        self.node_info.started_at = self.node_info.finished_at = current_time
        self.node_info.error = "Boo!"
        self.node_info.commit()

        row = db.model_query(db.Node).get(self.node_info.uuid)
        self.assertEqual(self.node_info.started_at, row.started_at)
        self.assertEqual(self.node_info.finished_at, row.finished_at)
        self.assertEqual(self.node_info.error, row.error)


class TestNodeInfoStateFsm(test_base.NodeStateTest):
    def test__get_fsm(self):
        self.node_info._fsm = None
        fsm = self.node_info._get_fsm()
        self.assertEqual(self.node_info.state, fsm.current_state)

    def test__get_fsm_invalid_state(self):
        self.node_info._fsm = None
        self.node_info._state = 'foo'
        six.assertRaisesRegex(self, automaton.exceptions.NotFound,
                              '.*undefined state.*',
                              self.node_info._get_fsm)

    def test__fsm_ctx_set_state(self):
        with self.node_info._fsm_ctx() as fsm:
            fsm.process_event(istate.Events.wait)
            self.assertEqual(self.node_info.state, istate.States.starting)
        self.assertEqual(self.node_info.state, istate.States.waiting)

    def test__fsm_ctx_set_same_state(self):
        version_id = self.node_info.version_id
        with self.node_info._fsm_ctx() as fsm:
            fsm.initialize(self.node_info.state)
        self.assertEqual(version_id, self.node_info.version_id)

    def test__fsm_ctx_illegal_event(self):
        with self.node_info._fsm_ctx() as fsm:
            six.assertRaisesRegex(self, automaton.exceptions.NotFound,
                                  'no defined transition', fsm.process_event,
                                  istate.Events.finish)
        self.assertEqual(self.node_info.state, istate.States.starting)

    def test__fsm_ctx_generic_exception(self):
        class CustomException(Exception):
            pass

        def func(fsm):
            fsm.process_event(istate.Events.wait)
            raise CustomException('Oops')

        with self.node_info._fsm_ctx() as fsm:
            self.assertRaises(CustomException, func, fsm)
        self.assertEqual(self.node_info.state, istate.States.waiting)

    def test_fsm_event(self):
        self.node_info.fsm_event(istate.Events.wait)
        self.assertEqual(self.node_info.state, istate.States.waiting)

    def test_fsm_illegal_event(self):
        six.assertRaisesRegex(self, utils.NodeStateInvalidEvent,
                              'no defined transition',
                              self.node_info.fsm_event, istate.Events.finish)
        self.assertEqual(self.node_info.state, istate.States.starting)

    def test_fsm_illegal_strict_event(self):
        six.assertRaisesRegex(self, utils.NodeStateInvalidEvent,
                              'no defined transition',
                              self.node_info.fsm_event,
                              istate.Events.finish, strict=True)
        self.assertIn('no defined transition', self.node_info.error)
        self.assertEqual(self.node_info.state, istate.States.error)


class TestFsmEvent(test_base.NodeStateTest):
    def test_event_before(self):
        @node_cache.fsm_event_before(istate.Events.wait)
        def function(node_info):
            self.assertEqual(node_info.state, istate.States.waiting)
            node_info.fsm_event(istate.Events.process)

        function(self.node_info)
        self.assertEqual(self.node_info.state, istate.States.processing)

    def test_event_after(self):
        @node_cache.fsm_event_after(istate.Events.process)
        def function(node_info):
            node_info.fsm_event(istate.Events.wait)
            self.assertEqual(node_info.state, istate.States.waiting)

        function(self.node_info)
        self.assertEqual(self.node_info.state, istate.States.processing)

    @mock.patch.object(node_cache, 'LOG', autospec=True)
    def test_triggers_fsm_error_transition_no_errors(self, log_mock):
        class CustomException(Exception):
            pass

        @node_cache.triggers_fsm_error_transition(no_errors=(CustomException,))
        def function(node_info):
            self.assertEqual(node_info.state, istate.States.starting)
            raise CustomException('Oops')

        function(self.node_info)
        log_msg = ('Not processing error event for the exception: '
                   '%(exc)s raised by %(func)s')
        log_mock.debug.assert_called_with(log_msg, mock.ANY,
                                          node_info=mock.ANY)
        self.assertEqual(self.node_info.state, istate.States.starting)

    def test_triggers_fsm_error_transition_no_errors_empty(self):
        class CustomException(Exception):
            pass

        @node_cache.triggers_fsm_error_transition(no_errors=())
        def function(node_info):
            self.assertEqual(node_info.state, istate.States.starting)
            raise CustomException('Oops!')

        # assert an error event was performed
        self.assertRaises(CustomException, function, self.node_info)
        self.assertEqual(self.node_info.state, istate.States.error)

    def test_triggers_fsm_error_transition_no_errors_with_error(self):
        class CustomException(Exception):
            pass

        @node_cache.triggers_fsm_error_transition(errors=(CustomException,))
        def function(node_info):
            self.assertEqual(node_info.state, istate.States.starting)
            raise CustomException('Oops')

        # assert a generic error triggers an error event
        self.assertRaises(CustomException, function, self.node_info)
        self.assertEqual(self.node_info.state, istate.States.error)

    def test_triggers_fsm_error_transition_erros_masked(self):
        class CustomException(Exception):
            pass

        @node_cache.triggers_fsm_error_transition(errors=())
        def function(node_info):
            self.assertEqual(node_info.state, istate.States.starting)
            raise CustomException('Oops')

        # assert no error event was triggered
        self.assertRaises(CustomException, function, self.node_info)
        self.assertEqual(self.node_info.state, istate.States.starting)

    def test_unlock(self):
        @node_cache.release_lock
        def func(node_info):
            self.assertTrue(node_info._lock.is_locked())

        self.node_info.acquire_lock(blocking=True)
        with mock.patch.object(self.node_info, 'release_lock',
                               autospec=True) as release_lock_mock:
            func(self.node_info)
        release_lock_mock.assert_called_once_with()

    def test_unlock_unlocked(self):
        @node_cache.release_lock
        def func(node_info):
            self.assertFalse(node_info._lock.is_locked())

        self.node_info.release_lock()
        with mock.patch.object(self.node_info, 'release_lock',
                               autospec=True) as release_lock_mock:
            func(self.node_info)
        self.assertEqual(0, release_lock_mock.call_count)

    @mock.patch.object(node_cache, 'triggers_fsm_error_transition',
                       autospec=True)
    @mock.patch.object(node_cache, 'fsm_event_after', autospec=True)
    def test_fsm_transition(self, fsm_event_after_mock, trigger_mock):
        @node_cache.fsm_transition(istate.Events.finish)
        def func():
            pass
        fsm_event_after_mock.assert_called_once_with(istate.Events.finish)
        trigger_mock.assert_called_once_with()

    @mock.patch.object(node_cache, 'triggers_fsm_error_transition',
                       autospec=True)
    @mock.patch.object(node_cache, 'fsm_event_before', autospec=True)
    def test_nonreentrant_fsm_transition(self, fsm_event_before_mock,
                                         trigger_mock):
        @node_cache.fsm_transition(istate.Events.abort, reentrant=False)
        def func():
            pass
        fsm_event_before_mock.assert_called_once_with(istate.Events.abort,
                                                      strict=True)
        trigger_mock.assert_called_once_with()


@mock.patch.object(node_cache, 'add_node', autospec=True)
@mock.patch.object(node_cache, 'NodeInfo', autospec=True)
class TestStartIntrospection(test_base.NodeTest):
    def prepare_mocks(fn):
        @six.wraps(fn)
        def inner(self, NodeMock, *args):
            method_mock = mock.Mock()
            NodeMock.return_value = self.node_info
            self.node_info.fsm_event = method_mock
            fn(self, method_mock, *args)
            method_mock.assert_called_once_with(istate.Events.start)
        return inner

    @prepare_mocks
    def test_node_in_db_ok_state(self, fsm_event_mock, add_node_mock):
        def side_effect(*args):
            self.node_info._state = 'foo'

        fsm_event_mock.side_effect = side_effect
        node_cache.start_introspection(self.node.uuid)
        add_node_mock.assert_called_once_with(self.node_info.uuid, 'foo')

    @prepare_mocks
    def test_node_in_db_invalid_state(self, fsm_event_mock, add_node_mock):
        fsm_event_mock.side_effect = utils.NodeStateInvalidEvent('Oops!')
        six.assertRaisesRegex(self, utils.NodeStateInvalidEvent, 'Oops!',
                              node_cache.start_introspection,
                              self.node_info.uuid)
        self.assertFalse(add_node_mock.called)

    @prepare_mocks
    def test_node_in_db_race_condition(self, fsm_event_mock, add_node_mock):
        fsm_event_mock.side_effect = utils.NodeStateRaceCondition()
        six.assertRaisesRegex(self, utils.NodeStateRaceCondition, '.*',
                              node_cache.start_introspection,
                              self.node_info.uuid)
        self.assertFalse(add_node_mock.called)

    @prepare_mocks
    def test_error_fsm_event(self, fsm_event_mock, add_node_mock):
        fsm_event_mock.side_effect = utils.Error('Oops!')
        six.assertRaisesRegex(self, utils.Error, 'Oops!',
                              node_cache.start_introspection,
                              self.node_info.uuid)
        self.assertFalse(add_node_mock.called)

    @prepare_mocks
    def test_node_not_in_db(self, fsm_event_mock, add_node_mock):
        fsm_event_mock.side_effect = utils.NotFoundInCacheError('Oops!')
        node_cache.start_introspection(self.node_info.uuid)
        add_node_mock.assert_called_once_with(self.node_info.uuid,
                                              istate.States.starting)

    @prepare_mocks
    def test_custom_exc_fsm_event(self, fsm_event_mock, add_node_mock):
        class CustomError(Exception):
            pass

        fsm_event_mock.side_effect = CustomError('Oops!')
        six.assertRaisesRegex(self, CustomError, 'Oops!',
                              node_cache.start_introspection,
                              self.node_info.uuid)
        self.assertFalse(add_node_mock.called)


class TestIntrospectionDataDbStore(test_base.NodeTest):
    def setUp(self):
        super(TestIntrospectionDataDbStore, self).setUp()
        node_cache.add_node(self.node.uuid,
                            istate.States.processing,
                            bmc_address='1.2.3.4')

    def _test_store_and_get(self, processed=False):
        node_cache.store_introspection_data(self.node.uuid,
                                            copy.deepcopy(self.data),
                                            processed=processed)
        stored_data = node_cache.get_introspection_data(self.node.uuid,
                                                        processed=processed)
        self.assertEqual(stored_data, self.data)

    def test_store_and_get_unprocessed(self):
        self._test_store_and_get(processed=False)

    def test_store_and_get_processed(self):
        self._test_store_and_get(processed=True)

    def test_get_no_data_available(self):
        self.assertRaises(utils.IntrospectionDataNotFound,
                          node_cache.get_introspection_data, self.node.uuid)

    def test_store_proc_and_unproc(self):
        unproc_data = {'s': 'value', 'b': True, 'i': 42}
        node_cache.store_introspection_data(self.node.uuid,
                                            unproc_data,
                                            processed=False)

        proc_data = {'foo': 'bar'}
        node_cache.store_introspection_data(self.node.uuid,
                                            proc_data,
                                            processed=True)

        stored_data = node_cache.get_introspection_data(self.node.uuid,
                                                        True)
        self.assertEqual(stored_data, proc_data)

        stored_data = node_cache.get_introspection_data(self.node.uuid,
                                                        False)
        self.assertEqual(stored_data, unproc_data)


@mock.patch.object(ir_utils, 'lookup_node', autospec=True)
class TestRecordNode(test_base.NodeTest):
    def setUp(self):
        super(TestRecordNode, self).setUp()
        self.node.provision_state = 'active'
        self.ironic = mock.Mock(spec=['node'],
                                node=mock.Mock(spec=['get']))
        self.ironic.node.get.return_value = self.node

    def test_no_lookup_data(self, mock_lookup):
        self.assertRaisesRegex(utils.NotFoundInCacheError,
                               'neither MAC addresses nor BMC addresses',
                               node_cache.record_node)

    def test_success(self, mock_lookup):
        mock_lookup.return_value = self.uuid
        result = node_cache.record_node(macs=self.macs, ironic=self.ironic)
        self.assertIsInstance(result, node_cache.NodeInfo)
        self.assertEqual(self.uuid, result.uuid)

    def test_not_found(self, mock_lookup):
        mock_lookup.return_value = None
        self.assertRaises(utils.NotFoundInCacheError,
                          node_cache.record_node,
                          macs=self.macs, ironic=self.ironic)

    def test_bad_provision_state(self, mock_lookup):
        mock_lookup.return_value = self.uuid
        self.node.provision_state = 'deploying'
        self.assertRaisesRegex(utils.Error, 'is not active',
                               node_cache.record_node,
                               macs=self.macs, ironic=self.ironic)
