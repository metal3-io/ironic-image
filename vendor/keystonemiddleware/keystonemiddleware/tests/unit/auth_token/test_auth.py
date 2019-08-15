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

import uuid

from keystoneauth1 import fixture
from keystoneauth1 import plugin as ksa_plugin
from keystoneauth1 import session
from oslo_log import log as logging
from requests_mock.contrib import fixture as rm_fixture
import six

from keystonemiddleware.auth_token import _auth
from keystonemiddleware.tests.unit import utils


class DefaultAuthPluginTests(utils.BaseTestCase):

    def new_plugin(self, auth_host=None, auth_port=None, auth_protocol=None,
                   auth_admin_prefix=None, admin_user=None,
                   admin_password=None, admin_tenant_name=None,
                   admin_token=None, identity_uri=None, log=None):
        if not log:
            log = self.logger

        return _auth.AuthTokenPlugin(
            auth_host=auth_host,
            auth_port=auth_port,
            auth_protocol=auth_protocol,
            auth_admin_prefix=auth_admin_prefix,
            admin_user=admin_user,
            admin_password=admin_password,
            admin_tenant_name=admin_tenant_name,
            admin_token=admin_token,
            identity_uri=identity_uri,
            log=log)

    def setUp(self):
        super(DefaultAuthPluginTests, self).setUp()

        self.stream = six.StringIO()
        self.logger = logging.getLogger(__name__)
        self.session = session.Session()
        self.requests_mock = self.useFixture(rm_fixture.Fixture())

    def test_auth_uri_from_fragments(self):
        auth_protocol = 'http'
        auth_host = 'testhost'
        auth_port = 8888
        auth_admin_prefix = 'admin'

        expected = '%s://%s:%d/admin' % (auth_protocol, auth_host, auth_port)

        plugin = self.new_plugin(auth_host=auth_host,
                                 auth_protocol=auth_protocol,
                                 auth_port=auth_port,
                                 auth_admin_prefix=auth_admin_prefix)

        endpoint = plugin.get_endpoint(self.session,
                                       interface=ksa_plugin.AUTH_INTERFACE)
        self.assertEqual(expected, endpoint)

    def test_identity_uri_overrides_fragments(self):
        identity_uri = 'http://testhost:8888/admin'
        plugin = self.new_plugin(identity_uri=identity_uri,
                                 auth_host='anotherhost',
                                 auth_port=9999,
                                 auth_protocol='ftp')

        endpoint = plugin.get_endpoint(self.session,
                                       interface=ksa_plugin.AUTH_INTERFACE)
        self.assertEqual(identity_uri, endpoint)

    def test_with_admin_token(self):
        token = uuid.uuid4().hex
        plugin = self.new_plugin(identity_uri='http://testhost:8888/admin',
                                 admin_token=token)
        self.assertEqual(token, plugin.get_token(self.session))

    def test_with_user_pass(self):
        base_uri = 'http://testhost:8888/admin'
        token = fixture.V2Token()
        admin_tenant_name = uuid.uuid4().hex

        self.requests_mock.post(base_uri + '/v2.0/tokens',
                                json=token)

        plugin = self.new_plugin(identity_uri=base_uri,
                                 admin_user=uuid.uuid4().hex,
                                 admin_password=uuid.uuid4().hex,
                                 admin_tenant_name=admin_tenant_name)

        self.assertEqual(token.token_id, plugin.get_token(self.session))
