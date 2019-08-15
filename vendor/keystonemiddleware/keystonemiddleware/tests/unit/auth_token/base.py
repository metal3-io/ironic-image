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

import fixtures
from oslo_config import cfg
from oslo_config import fixture as cfg_fixture
from oslo_log import log as logging
from requests_mock.contrib import fixture as rm_fixture
import six
from six.moves import http_client
import webob.dec

from keystonemiddleware import auth_token
from keystonemiddleware.tests.unit import utils


class BaseAuthTokenTestCase(utils.MiddlewareTestCase):

    def setUp(self):
        super(BaseAuthTokenTestCase, self).setUp()
        self.requests_mock = self.useFixture(rm_fixture.Fixture())
        self.logger = fixtures.FakeLogger(level=logging.DEBUG)
        self.cfg = self.useFixture(cfg_fixture.Config(conf=cfg.ConfigOpts()))
        self.cfg.conf(args=[])

    def create_middleware(self, cb, conf=None, use_global_conf=False):

        @webob.dec.wsgify
        def _do_cb(req):
            return cb(req)

        if use_global_conf:
            opts = conf or {}
        else:
            opts = {
                'oslo_config_config': self.cfg.conf,
            }
            opts.update(conf or {})

        return auth_token.AuthProtocol(_do_cb, opts)

    def call(self, middleware, method='GET', path='/', headers=None,
             expected_status=http_client.OK,
             expected_body_string=None):
        req = webob.Request.blank(path)
        req.method = method

        for k, v in (headers or {}).items():
            req.headers[k] = v

        resp = req.get_response(middleware)
        self.assertEqual(expected_status, resp.status_int)
        if expected_body_string:
            self.assertIn(expected_body_string, six.text_type(resp.body))
        resp.request = req
        return resp
