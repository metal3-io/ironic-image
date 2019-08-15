# Copyright 2013 Hewlett-Packard Development Company, L.P.
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

# Mostly copied from ironic/tests/test_swift.py

from keystoneauth1 import exceptions as ks_exc
import mock
import openstack
from openstack import exceptions as os_exc

from ironic_inspector.common import keystone
from ironic_inspector.common import swift
from ironic_inspector.test import base as test_base
from ironic_inspector import utils


@mock.patch.object(keystone, 'get_session', autospec=True)
@mock.patch.object(openstack.connection, 'Connection', autospec=True)
class SwiftTestCase(test_base.NodeTest):

    def setUp(self):
        super(SwiftTestCase, self).setUp()
        swift.reset_swift_session()
        self.addCleanup(swift.reset_swift_session)

    def test___init__(self, connection_mock, load_mock):
        swift.SwiftAPI()
        connection_mock.assert_called_once_with(
            session=load_mock.return_value,
            oslo_conf=swift.CONF)

    def test___init__keystone_failure(self, connection_mock, load_mock):
        load_mock.side_effect = ks_exc.MissingRequiredOptions([])
        self.assertRaisesRegex(utils.Error, 'Could not connect',
                               swift.SwiftAPI)
        self.assertFalse(connection_mock.called)

    def test___init__sdk_failure(self, connection_mock, load_mock):
        connection_mock.side_effect = RuntimeError()
        self.assertRaisesRegex(utils.Error, 'Could not connect',
                               swift.SwiftAPI)
        connection_mock.assert_called_once_with(
            session=load_mock.return_value,
            oslo_conf=swift.CONF)

    def test_create_object(self, connection_mock, load_mock):
        swiftapi = swift.SwiftAPI()
        swift_mock = connection_mock.return_value.object_store
        swift_mock.create_object.return_value = 'object-uuid'

        object_uuid = swiftapi.create_object('object', 'some-string-data')

        swift_mock.create_container.assert_called_once_with('ironic-inspector')
        swift_mock.create_object.assert_called_once_with(
            'ironic-inspector', 'object',
            data='some-string-data', headers=None)
        self.assertEqual('object-uuid', object_uuid)

    def test_create_object_with_delete_after(self, connection_mock, load_mock):
        swift.CONF.set_override('delete_after', 60, group='swift')

        swiftapi = swift.SwiftAPI()
        swift_mock = connection_mock.return_value.object_store
        swift_mock.create_object.return_value = 'object-uuid'

        object_uuid = swiftapi.create_object('object', 'some-string-data')

        swift_mock.create_container.assert_called_once_with('ironic-inspector')
        swift_mock.create_object.assert_called_once_with(
            'ironic-inspector', 'object',
            data='some-string-data', headers={'X-Delete-After': 60})
        self.assertEqual('object-uuid', object_uuid)

    def test_create_object_create_container_fails(
            self, connection_mock, load_mock):
        swiftapi = swift.SwiftAPI()
        swift_mock = connection_mock.return_value.object_store
        swift_mock.create_container.side_effect = os_exc.SDKException
        self.assertRaises(utils.Error, swiftapi.create_object, 'object',
                          'some-string-data')
        swift_mock.create_container.assert_called_once_with('ironic-inspector')
        self.assertFalse(swift_mock.create_object.called)

    def test_create_object_put_object_fails(self, connection_mock, load_mock):
        swiftapi = swift.SwiftAPI()
        swift_mock = connection_mock.return_value.object_store
        swift_mock.create_object.side_effect = os_exc.SDKException
        self.assertRaises(utils.Error, swiftapi.create_object, 'object',
                          'some-string-data')
        swift_mock.create_container.assert_called_once_with('ironic-inspector')
        swift_mock.create_object.assert_called_once_with(
            'ironic-inspector', 'object',
            data='some-string-data', headers=None)

    def test_get_object(self, connection_mock, load_mock):
        swiftapi = swift.SwiftAPI()
        swift_mock = connection_mock.return_value.object_store

        swift_obj = swiftapi.get_object('object')

        swift_mock.download_object.assert_called_once_with(
            'object', container='ironic-inspector')
        self.assertIs(swift_mock.download_object.return_value, swift_obj)

    def test_get_object_fails(self, connection_mock, load_mock):
        swiftapi = swift.SwiftAPI()
        swift_mock = connection_mock.return_value.object_store
        swift_mock.download_object.side_effect = os_exc.SDKException
        self.assertRaises(utils.Error, swiftapi.get_object,
                          'object')
        swift_mock.download_object.assert_called_once_with(
            'object', container='ironic-inspector')
