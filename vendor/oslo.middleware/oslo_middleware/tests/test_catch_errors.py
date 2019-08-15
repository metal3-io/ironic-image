# Copyright (c) 2013 NEC Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import fixtures
import mock
from oslotest import base as test_base
import webob.dec
import webob.exc

from oslo_middleware import catch_errors


class CatchErrorsTest(test_base.BaseTestCase):

    def _test_has_request_id(self, application, expected_code=None):
        app = catch_errors.CatchErrors(application)
        req = webob.Request.blank('/test')
        req.environ['HTTP_X_AUTH_TOKEN'] = 'hello=world'
        res = req.get_response(app)
        self.assertEqual(expected_code, res.status_int)

    def test_success_response(self):
        @webob.dec.wsgify
        def application(req):
            return 'Hello, World!!!'

        self._test_has_request_id(application, webob.exc.HTTPOk.code)

    def test_internal_server_error(self):
        @webob.dec.wsgify
        def application(req):
            raise Exception()

        with mock.patch.object(catch_errors.LOG, 'exception') as log_exc:
            self._test_has_request_id(application,
                                      webob.exc.HTTPInternalServerError.code)
            self.assertEqual(1, log_exc.call_count)
            req_log = log_exc.call_args[0][1]
            self.assertIn('X-Auth-Token: *****', str(req_log))

    def test_filter_tokens_from_log(self):
        logger = self.useFixture(fixtures.FakeLogger(nuke_handlers=False))

        @webob.dec.wsgify
        def application(req):
            raise Exception()

        app = catch_errors.CatchErrors(application)
        req = webob.Request.blank('/test',
                                  text=u'test data',
                                  method='POST',
                                  headers={'X-Auth-Token': 'secret1',
                                           'X-Service-Token': 'secret2',
                                           'X-Other-Token': 'secret3'})
        res = req.get_response(app)
        self.assertEqual(500, res.status_int)

        output = logger.output

        self.assertIn('X-Auth-Token: *****', output)
        self.assertIn('X-Service-Token: *****', output)
        self.assertIn('X-Other-Token: *****', output)
        self.assertIn('test data', output)
