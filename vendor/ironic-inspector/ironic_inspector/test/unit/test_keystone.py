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

from keystoneauth1 import loading as kaloading
import mock
from oslo_config import cfg

from ironic_inspector.common import keystone
from ironic_inspector.test import base


TESTGROUP = 'keystone_test'


class KeystoneTest(base.BaseTest):

    def setUp(self):
        super(KeystoneTest, self).setUp()
        self.cfg.conf.register_group(cfg.OptGroup(TESTGROUP))

    def test_register_auth_opts(self):
        keystone.register_auth_opts(TESTGROUP, 'fake-service')
        auth_opts = ['auth_type', 'auth_section']
        sess_opts = ['certfile', 'keyfile', 'insecure', 'timeout', 'cafile']
        for o in auth_opts + sess_opts:
            self.assertIn(o, self.cfg.conf[TESTGROUP])
        self.assertEqual('password', self.cfg.conf[TESTGROUP]['auth_type'])
        self.assertEqual('fake-service',
                         self.cfg.conf[TESTGROUP]['service_type'])

    @mock.patch.object(kaloading, 'load_auth_from_conf_options', autospec=True)
    def test_get_session(self, auth_mock):
        keystone.register_auth_opts(TESTGROUP, 'fake-service')
        self.cfg.config(group=TESTGROUP,
                        cafile='/path/to/ca/file')
        auth1 = mock.Mock()
        auth_mock.return_value = auth1
        sess = keystone.get_session(TESTGROUP)
        self.assertEqual('/path/to/ca/file', sess.verify)
        self.assertEqual(auth1, sess.auth)

    def test_add_auth_options(self):
        opts = keystone.add_auth_options([], 'fake-service')
        # check that there is no duplicates
        names = {o.dest for o in opts}
        self.assertEqual(len(names), len(opts))
        # NOTE(pas-ha) checking for most standard auth and session ones only
        expected = {'timeout', 'insecure', 'cafile', 'certfile', 'keyfile',
                    'auth_type', 'auth_url', 'username', 'password',
                    'tenant_name', 'project_name', 'trust_id',
                    'domain_id', 'user_domain_id', 'project_domain_id'}
        self.assertTrue(expected.issubset(names))
