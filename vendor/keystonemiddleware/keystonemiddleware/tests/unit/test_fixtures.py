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

import datetime
import uuid

from oslo_utils import timeutils

from keystonemiddleware import fixture
from keystonemiddleware.tests.unit.auth_token import test_auth_token_middleware


class AuthTokenFixtureTest(
        test_auth_token_middleware.BaseAuthTokenMiddlewareTest):

    def setUp(self):
        self.token_id = uuid.uuid4().hex
        self.user_id = uuid.uuid4().hex
        self.username = uuid.uuid4().hex
        self.project_id = uuid.uuid4().hex
        self.project_name = uuid.uuid4().hex
        self.role_list = [uuid.uuid4().hex, uuid.uuid4().hex]
        super(AuthTokenFixtureTest, self).setUp()

        self.atm_fixture = self.useFixture(fixture.AuthTokenFixture())
        self.atm_fixture.add_token_data(token_id=self.token_id,
                                        user_id=self.user_id,
                                        user_name=self.username,
                                        role_list=self.role_list,
                                        project_id=self.project_id,
                                        project_name=self.project_name)
        self.set_middleware()
        self.middleware._app.expected_env = {
            'HTTP_X_USER_ID': self.user_id,
            'HTTP_X_USER_NAME': self.username,
            'HTTP_X_PROJECT_ID': self.project_id,
            'HTTP_X_PROJECT_NAME': self.project_name,
            'HTTP_X_ROLES': ','.join(self.role_list)}

    def test_auth_token_fixture_valid_token(self):
        resp = self.call_middleware(headers={'X-Auth-Token': self.token_id})
        self.assertIn('keystone.token_info', resp.request.environ)

    def test_auth_token_fixture_invalid_token(self):
        self.call_middleware(
            headers={'X-Auth-Token': uuid.uuid4().hex}, expected_status=401)

    def test_auth_token_fixture_expired_token(self):
        expired_token_id = uuid.uuid4().hex
        self.atm_fixture.add_token_data(
            token_id=expired_token_id,
            user_id=self.user_id,
            role_list=self.role_list,
            expires=(timeutils.utcnow() - datetime.timedelta(seconds=86400)))
        self.call_middleware(
            headers={'X-Auth-Token': expired_token_id}, expected_status=401)
