# Copyright (c) 2015 Thales Services SAS
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

from oslo_config import fixture as config
from oslotest import base
import webob

from oslo_middleware import ssl


class SSLMiddlewareTest(base.BaseTestCase):

    def setUp(self):
        super(SSLMiddlewareTest, self).setUp()
        self.useFixture(config.Config())

    def _test_scheme(self, expected, headers, secure_proxy_ssl_header=None):
        middleware = ssl.SSLMiddleware(None)
        if secure_proxy_ssl_header:
            middleware.oslo_conf.set_override(
                'secure_proxy_ssl_header', secure_proxy_ssl_header,
                group='oslo_middleware')
        request = webob.Request.blank('http://example.com/', headers=headers)

        # Ensure ssl middleware does not stop pipeline execution
        self.assertIsNone(middleware.process_request(request))

        self.assertEqual(expected, request.scheme)

    def test_without_forwarded_protocol(self):
        self._test_scheme('http', {})

    def test_with_forwarded_protocol(self):
        headers = {'X-Forwarded-Proto': 'https'}
        self._test_scheme('https', headers)

    def test_with_custom_header(self):
        headers = {'X-Forwarded-Proto': 'https'}
        self._test_scheme('http', headers,
                          secure_proxy_ssl_header='X-My-Header')

    def test_with_custom_header_and_forwarded_protocol(self):
        headers = {'X-My-Header': 'https'}
        self._test_scheme('https', headers,
                          secure_proxy_ssl_header='X-My-Header')
