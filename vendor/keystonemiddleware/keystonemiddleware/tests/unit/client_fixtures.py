# Copyright 2013 OpenStack Foundation
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

import os
import uuid

import fixtures
from keystoneauth1 import fixture
from oslo_serialization import jsonutils
import testresources


TESTDIR = os.path.dirname(os.path.abspath(__file__))
ROOTDIR = os.path.normpath(os.path.join(TESTDIR, '..', '..', '..'))


class Examples(fixtures.Fixture):
    """Example tokens and certs loaded from the examples directory.

    To use this class correctly, the module needs to override the test suite
    class to use testresources.OptimisingTestSuite (otherwise the files will
    be read on every test). This is done by defining a load_tests function
    in the module, like this:

    def load_tests(loader, tests, pattern):
        return testresources.OptimisingTestSuite(tests)

    (see http://docs.python.org/2/library/unittest.html#load-tests-protocol )

    """

    def setUp(self):
        super(Examples, self).setUp()

        self.KERBEROS_BIND = 'USER@REALM'
        self.SERVICE_KERBEROS_BIND = 'SERVICE_USER@SERVICE_REALM'

        self.UUID_TOKEN_DEFAULT = "ec6c0710ec2f471498484c1b53ab4f9d"
        self.UUID_TOKEN_NO_SERVICE_CATALOG = '8286720fbe4941e69fa8241723bb02df'
        self.UUID_TOKEN_UNSCOPED = '731f903721c14827be7b2dc912af7776'
        self.UUID_TOKEN_BIND = '3fc54048ad64405c98225ce0897af7c5'
        self.UUID_TOKEN_UNKNOWN_BIND = '8885fdf4d42e4fb9879e6379fa1eaf48'
        self.v3_UUID_TOKEN_DEFAULT = '5603457654b346fdbb93437bfe76f2f1'
        self.v3_UUID_TOKEN_UNSCOPED = 'd34835fdaec447e695a0a024d84f8d79'
        self.v3_UUID_TOKEN_DOMAIN_SCOPED = 'e8a7b63aaa4449f38f0c5c05c3581792'
        self.v3_UUID_TOKEN_BIND = '2f61f73e1c854cbb9534c487f9bd63c2'
        self.v3_UUID_TOKEN_UNKNOWN_BIND = '7ed9781b62cd4880b8d8c6788ab1d1e2'
        self.v3_SYSTEM_SCOPED_TOKEN = '9ca6e88364b6418a88ffc02e6a24afd8'

        self.UUID_SERVICE_TOKEN_DEFAULT = 'fe4c0710ec2f492748596c1b53ab124'
        self.UUID_SERVICE_TOKEN_BIND = '5e43439613d34a13a7e03b2762bd08ab'
        self.v3_UUID_SERVICE_TOKEN_DEFAULT = 'g431071bbc2f492748596c1b53cb229'
        self.v3_UUID_SERVICE_TOKEN_BIND = 'be705e4426d0449a89e35ae21c380a05'
        self.v3_NOT_IS_ADMIN_PROJECT = uuid.uuid4().hex

        self.v3_APP_CRED_TOKEN = '6f506fa9641448bbaecbd12dd30678a9'
        self.v3_APP_CRED_ACCESS_RULES = 'c417747898c44629b08791f2579e40a5'
        self.v3_APP_CRED_EMPTY_ACCESS_RULES = 'c75905c307f04fdd9979126582d7aae'
        self.v3_APP_CRED_MATCHING_RULES = 'ad49decc7106489d95ca9ed874b6cb66'

        # JSON responses keyed by token ID
        self.TOKEN_RESPONSES = {}

        # basic values
        PROJECT_ID = 'tenant_id1'
        PROJECT_NAME = 'tenant_name1'
        USER_ID = 'user_id1'
        USER_NAME = 'user_name1'
        DOMAIN_ID = 'domain_id1'
        DOMAIN_NAME = 'domain_name1'
        ROLE_NAME1 = 'role1'
        ROLE_NAME2 = 'role2'

        SERVICE_PROJECT_ID = 'service_project_id1'
        SERVICE_PROJECT_NAME = 'service_project_name1'
        SERVICE_USER_ID = 'service_user_id1'
        SERVICE_USER_NAME = 'service_user_name1'
        SERVICE_DOMAIN_ID = 'service_domain_id1'
        SERVICE_DOMAIN_NAME = 'service_domain_name1'
        SERVICE_ROLE_NAME1 = 'service'
        SERVICE_ROLE_NAME2 = 'service_role2'

        APP_CRED_ID = 'app_cred_id1'

        self.SERVICE_TYPE = 'identity'
        self.UNVERSIONED_SERVICE_URL = 'https://keystone.example.com:1234/'
        self.SERVICE_URL = self.UNVERSIONED_SERVICE_URL + 'v2.0'

        # Generated V2 Tokens

        token = fixture.V2Token(token_id=self.UUID_TOKEN_DEFAULT,
                                tenant_id=PROJECT_ID,
                                tenant_name=PROJECT_NAME,
                                user_id=USER_ID,
                                user_name=USER_NAME)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint(public=self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.UUID_TOKEN_DEFAULT] = token

        token = fixture.V2Token(token_id=self.UUID_TOKEN_UNSCOPED,
                                user_id=USER_ID,
                                user_name=USER_NAME)
        self.TOKEN_RESPONSES[self.UUID_TOKEN_UNSCOPED] = token

        token = fixture.V2Token(token_id='valid-token',
                                tenant_id=PROJECT_ID,
                                tenant_name=PROJECT_NAME,
                                user_id=USER_ID,
                                user_name=USER_NAME)
        token.add_role(ROLE_NAME1)
        token.add_role(ROLE_NAME2)
        self.TOKEN_RESPONSES[self.UUID_TOKEN_NO_SERVICE_CATALOG] = token

        token = fixture.V2Token(token_id=self.UUID_TOKEN_BIND,
                                tenant_id=PROJECT_ID,
                                tenant_name=PROJECT_NAME,
                                user_id=USER_ID,
                                user_name=USER_NAME)
        token.add_role(ROLE_NAME1)
        token.add_role(ROLE_NAME2)
        token['access']['token']['bind'] = {'kerberos': self.KERBEROS_BIND}
        self.TOKEN_RESPONSES[self.UUID_TOKEN_BIND] = token

        token = fixture.V2Token(token_id=self.UUID_SERVICE_TOKEN_BIND,
                                tenant_id=SERVICE_PROJECT_ID,
                                tenant_name=SERVICE_PROJECT_NAME,
                                user_id=SERVICE_USER_ID,
                                user_name=SERVICE_USER_NAME)
        token.add_role(SERVICE_ROLE_NAME1)
        token.add_role(SERVICE_ROLE_NAME2)
        token['access']['token']['bind'] = {
            'kerberos': self.SERVICE_KERBEROS_BIND}
        self.TOKEN_RESPONSES[self.UUID_SERVICE_TOKEN_BIND] = token

        token = fixture.V2Token(token_id=self.UUID_TOKEN_UNKNOWN_BIND,
                                tenant_id=PROJECT_ID,
                                tenant_name=PROJECT_NAME,
                                user_id=USER_ID,
                                user_name=USER_NAME)
        token.add_role(ROLE_NAME1)
        token.add_role(ROLE_NAME2)
        token['access']['token']['bind'] = {'FOO': 'BAR'}
        self.TOKEN_RESPONSES[self.UUID_TOKEN_UNKNOWN_BIND] = token

        token = fixture.V2Token(token_id=self.UUID_SERVICE_TOKEN_DEFAULT,
                                tenant_id=SERVICE_PROJECT_ID,
                                tenant_name=SERVICE_PROJECT_NAME,
                                user_id=SERVICE_USER_ID,
                                user_name=SERVICE_USER_NAME)
        token.add_role(name=SERVICE_ROLE_NAME1)
        token.add_role(name=SERVICE_ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint(public=self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.UUID_SERVICE_TOKEN_DEFAULT] = token

        # Generated V3 Tokens

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME,
                                project_id=PROJECT_ID,
                                project_name=PROJECT_NAME,
                                project_domain_id=DOMAIN_ID,
                                project_domain_name=DOMAIN_NAME)
        token.add_role(id=ROLE_NAME1, name=ROLE_NAME1)
        token.add_role(id=ROLE_NAME2, name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.v3_UUID_TOKEN_DEFAULT] = token

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME)
        self.TOKEN_RESPONSES[self.v3_UUID_TOKEN_UNSCOPED] = token

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME)
        token.system = {'all': True}
        token.add_role(id=ROLE_NAME1, name=ROLE_NAME1)
        token.add_role(id=ROLE_NAME2, name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.v3_SYSTEM_SCOPED_TOKEN] = token

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME,
                                domain_id=DOMAIN_ID,
                                domain_name=DOMAIN_NAME)
        token.add_role(id=ROLE_NAME1, name=ROLE_NAME1)
        token.add_role(id=ROLE_NAME2, name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.v3_UUID_TOKEN_DOMAIN_SCOPED] = token

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME,
                                project_id=PROJECT_ID,
                                project_name=PROJECT_NAME,
                                project_domain_id=DOMAIN_ID,
                                project_domain_name=DOMAIN_NAME)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME,
                                project_id=PROJECT_ID,
                                project_name=PROJECT_NAME,
                                project_domain_id=DOMAIN_ID,
                                project_domain_name=DOMAIN_NAME)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        token['token']['bind'] = {'kerberos': self.KERBEROS_BIND}
        self.TOKEN_RESPONSES[self.v3_UUID_TOKEN_BIND] = token

        token = fixture.V3Token(user_id=SERVICE_USER_ID,
                                user_name=SERVICE_USER_NAME,
                                user_domain_id=SERVICE_DOMAIN_ID,
                                user_domain_name=SERVICE_DOMAIN_NAME,
                                project_id=SERVICE_PROJECT_ID,
                                project_name=SERVICE_PROJECT_NAME,
                                project_domain_id=SERVICE_DOMAIN_ID,
                                project_domain_name=SERVICE_DOMAIN_NAME)
        token.add_role(name=SERVICE_ROLE_NAME1)
        token.add_role(name=SERVICE_ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        token['token']['bind'] = {'kerberos': self.SERVICE_KERBEROS_BIND}
        self.TOKEN_RESPONSES[self.v3_UUID_SERVICE_TOKEN_BIND] = token

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME,
                                project_id=PROJECT_ID,
                                project_name=PROJECT_NAME,
                                project_domain_id=DOMAIN_ID,
                                project_domain_name=DOMAIN_NAME)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        token['token']['bind'] = {'FOO': 'BAR'}
        self.TOKEN_RESPONSES[self.v3_UUID_TOKEN_UNKNOWN_BIND] = token

        token = fixture.V3Token(user_id=SERVICE_USER_ID,
                                user_name=SERVICE_USER_NAME,
                                user_domain_id=SERVICE_DOMAIN_ID,
                                user_domain_name=SERVICE_DOMAIN_NAME,
                                project_id=SERVICE_PROJECT_ID,
                                project_name=SERVICE_PROJECT_NAME,
                                project_domain_id=SERVICE_DOMAIN_ID,
                                project_domain_name=SERVICE_DOMAIN_NAME)
        token.add_role(id=SERVICE_ROLE_NAME1,
                       name=SERVICE_ROLE_NAME1)
        token.add_role(id=SERVICE_ROLE_NAME2,
                       name=SERVICE_ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.v3_UUID_SERVICE_TOKEN_DEFAULT] = token

        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME,
                                project_id=PROJECT_ID,
                                project_name=PROJECT_NAME,
                                project_domain_id=DOMAIN_ID,
                                project_domain_name=DOMAIN_NAME,
                                is_admin_project=False)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.v3_NOT_IS_ADMIN_PROJECT] = token

        # Application credential token
        token = fixture.V3Token(user_id=USER_ID,
                                user_name=USER_NAME,
                                user_domain_id=DOMAIN_ID,
                                user_domain_name=DOMAIN_NAME,
                                project_id=PROJECT_ID,
                                project_name=PROJECT_NAME,
                                project_domain_id=DOMAIN_ID,
                                project_domain_name=DOMAIN_NAME,
                                application_credential_id=APP_CRED_ID)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        svc = token.add_service('compute')
        svc.add_endpoint('public', 'https://nova.openstack.example.org/v2.1')
        self.TOKEN_RESPONSES[self.v3_APP_CRED_TOKEN] = token

        # Application credential with access_rules token
        access_rules = [{
            'path': '/v2.1/servers',
            'method': 'GET',
            'service': 'compute'
        }]
        token = fixture.V3Token(
            user_id=USER_ID,
            user_name=USER_NAME,
            user_domain_id=DOMAIN_ID,
            user_domain_name=DOMAIN_NAME,
            project_id=PROJECT_ID,
            project_name=PROJECT_NAME,
            project_domain_id=DOMAIN_ID,
            project_domain_name=DOMAIN_NAME,
            application_credential_id=APP_CRED_ID,
            application_credential_access_rules=access_rules)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        svc = token.add_service('compute')
        svc.add_endpoint('public', 'https://nova.openstack.example.org')
        svc = token.add_service('image')
        svc.add_endpoint('public', 'https://glance.openstack.example.org')
        self.TOKEN_RESPONSES[self.v3_APP_CRED_ACCESS_RULES] = token

        # Application credential with explicitly empty access_rules
        access_rules = []
        token = fixture.V3Token(
            user_id=USER_ID,
            user_name=USER_NAME,
            user_domain_id=DOMAIN_ID,
            user_domain_name=DOMAIN_NAME,
            project_id=PROJECT_ID,
            project_name=PROJECT_NAME,
            project_domain_id=DOMAIN_ID,
            project_domain_name=DOMAIN_NAME,
            application_credential_id=APP_CRED_ID,
            application_credential_access_rules=access_rules)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        self.TOKEN_RESPONSES[self.v3_APP_CRED_EMPTY_ACCESS_RULES] = token

        # Application credential with matching rules
        access_rules = [
            {
                'path': '/v2.1/servers/{server_id}',
                'method': 'GET',
                'service': 'compute'
            },
            {
                'path': '/v2/images/*',
                'method': 'GET',
                'service': 'image'
            },
            {
                'path': '**',
                'method': 'GET',
                'service': 'identity'
            },
            {
                'path': '/v3/{project_id}/types/{volume_type_id}',
                'method': 'GET',
                'service': 'block-storage'
            },
            {
                'path': '/v1/*/*/*',
                'method': 'GET',
                'service': 'object-store'
            }
        ]
        token = fixture.V3Token(
            user_id=USER_ID,
            user_name=USER_NAME,
            user_domain_id=DOMAIN_ID,
            user_domain_name=DOMAIN_NAME,
            project_id=PROJECT_ID,
            project_name=PROJECT_NAME,
            project_domain_id=DOMAIN_ID,
            project_domain_name=DOMAIN_NAME,
            application_credential_id=APP_CRED_ID,
            application_credential_access_rules=access_rules)
        token.add_role(name=ROLE_NAME1)
        token.add_role(name=ROLE_NAME2)
        svc = token.add_service(self.SERVICE_TYPE)
        svc.add_endpoint('public', self.SERVICE_URL)
        svc = token.add_service('compute')
        svc.add_endpoint('public', 'https://nova.openstack.example.org')
        svc = token.add_service('image')
        svc.add_endpoint('public', 'https://glance.openstack.example.org')
        svc = token.add_service('block-storage')
        svc.add_endpoint('public', 'https://cinder.openstack.example.org')
        svc = token.add_service('object-store')
        svc.add_endpoint('public', 'https://swift.openstack.example.org')
        self.TOKEN_RESPONSES[self.v3_APP_CRED_MATCHING_RULES] = token

        self.JSON_TOKEN_RESPONSES = dict([(k, jsonutils.dumps(v)) for k, v in
                                          self.TOKEN_RESPONSES.items()])


EXAMPLES_RESOURCE = testresources.FixtureResource(Examples())
