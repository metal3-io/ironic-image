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

import eventlet  # noqa
import fixtures
from oslo_config import cfg

from ironic_inspector.test import base as test_base
from ironic_inspector import wsgi_service

CONF = cfg.CONF


class BaseWSGITest(test_base.BaseTest):
    def setUp(self):
        # generic mocks setUp method
        super(BaseWSGITest, self).setUp()
        self.app = self.useFixture(fixtures.MockPatchObject(
            wsgi_service.app, 'app', autospec=True)).mock
        self.server = self.useFixture(fixtures.MockPatchObject(
            wsgi_service.wsgi, 'Server', autospec=True)).mock
        self.mock_log = self.useFixture(fixtures.MockPatchObject(
            wsgi_service, 'LOG')).mock
        self.service = wsgi_service.WSGIService()
        self.service.server = self.server


class TestWSGIServiceInitMiddleware(BaseWSGITest):
    def setUp(self):
        super(TestWSGIServiceInitMiddleware, self).setUp()
        self.mock_add_auth_middleware = self.useFixture(
            fixtures.MockPatchObject(wsgi_service.utils,
                                     'add_auth_middleware')).mock
        self.mock_add_cors_middleware = self.useFixture(
            fixtures.MockPatchObject(wsgi_service.utils,
                                     'add_cors_middleware')).mock
        # 'positive' settings
        CONF.set_override('auth_strategy', 'keystone')
        CONF.set_override('store_data', 'swift', 'processing')

    def test_init_middleware(self):
        self.service._init_middleware()

        self.mock_add_auth_middleware.assert_called_once_with(self.app)
        self.mock_add_cors_middleware.assert_called_once_with(self.app)

    def test_init_middleware_noauth(self):
        CONF.set_override('auth_strategy', 'noauth')
        self.service._init_middleware()

        self.mock_add_auth_middleware.assert_not_called()
        self.mock_log.warning.assert_called_once_with(
            'Starting unauthenticated, please check configuration')
        self.mock_add_cors_middleware.assert_called_once_with(self.app)


class TestWSGIService(BaseWSGITest):
    def setUp(self):
        super(TestWSGIService, self).setUp()
        self.mock__init_middleware = self.useFixture(fixtures.MockPatchObject(
            self.service, '_init_middleware')).mock

        # 'positive' settings
        CONF.set_override('listen_address', '42.42.42.42')
        CONF.set_override('listen_port', 42)

    def test_start(self):
        self.service.start()

        self.mock__init_middleware.assert_called_once_with()
        self.server.start.assert_called_once_with()

    def test_stop(self):
        self.service.stop()
        self.server.stop.assert_called_once_with()

    def test_wait(self):
        self.service.wait()
        self.server.wait.assert_called_once_with()

    def test_reset(self):
        self.service.reset()
        self.server.reset.assert_called_once_with()
