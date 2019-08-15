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

import json

import fixtures
import mock
from oslo_config import cfg

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import db
from ironic_inspector import introspection_state as istate
from ironic_inspector.plugins import introspection_data
from ironic_inspector.test import base as test_base

CONF = cfg.CONF


class BaseTest(test_base.NodeTest):
    data = {
        'ipmi_address': '1.2.3.4',
        'cpus': 2,
        'cpu_arch': 'x86_64',
        'memory_mb': 1024,
        'local_gb': 20,
        'interfaces': {
            'em1': {'mac': '11:22:33:44:55:66', 'ip': '1.2.0.1'},
        }
    }

    def setUp(self):
        super(BaseTest, self).setUp()
        self.cli_fixture = self.useFixture(
            fixtures.MockPatchObject(ir_utils, 'get_client', autospec=True))
        self.cli = self.cli_fixture.mock.return_value


@mock.patch.object(introspection_data.swift, 'SwiftAPI', autospec=True)
class TestSwiftStore(BaseTest):

    def setUp(self):
        super(TestSwiftStore, self).setUp()
        self.driver = introspection_data.SwiftStore()

    def test_get_data(self, swift_mock):
        swift_conn = swift_mock.return_value
        swift_conn.get_object.return_value = json.dumps(self.data)
        name = 'inspector_data-%s' % self.uuid

        res_data = self.driver.get(self.uuid)

        swift_conn.get_object.assert_called_once_with(name)
        self.assertEqual(self.data, json.loads(res_data))

    def test_store_data(self, swift_mock):
        swift_conn = swift_mock.return_value
        name = 'inspector_data-%s' % self.uuid

        self.driver.save(self.node_info, self.data)

        data = introspection_data._filter_data_excluded_keys(self.data)
        swift_conn.create_object.assert_called_once_with(name,
                                                         json.dumps(data))

    def _create_node(self):
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.node_info.uuid,
                    state=istate.States.starting).save(session)


class TestDatabaseStore(BaseTest):
    def setUp(self):
        super(TestDatabaseStore, self).setUp()
        self.driver = introspection_data.DatabaseStore()
        session = db.get_writer_session()
        with session.begin():
            db.Node(uuid=self.node_info.uuid,
                    state=istate.States.starting).save(session)

    def test_store_and_get_data(self):
        self.driver.save(self.node_info.uuid, self.data)

        res_data = self.driver.get(self.node_info.uuid)

        self.assertEqual(self.data, json.loads(res_data))
