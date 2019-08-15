# Copyright (c) 2012 Red Hat, Inc.
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
from oslotest import base as test_base
import six
import webob

from oslo_middleware import sizelimit


class TestLimitingReader(test_base.BaseTestCase):

    def test_limiting_reader(self):
        BYTES = 1024
        bytes_read = 0
        data = six.StringIO("*" * BYTES)
        for chunk in sizelimit.LimitingReader(data, BYTES):
            bytes_read += len(chunk)

        self.assertEqual(BYTES, bytes_read)

        bytes_read = 0
        data = six.StringIO("*" * BYTES)
        reader = sizelimit.LimitingReader(data, BYTES)
        byte = reader.read(1)
        while len(byte) != 0:
            bytes_read += 1
            byte = reader.read(1)

        self.assertEqual(BYTES, bytes_read)

    def test_read_default_value(self):
        BYTES = 1024
        data_str = "*" * BYTES
        data = six.StringIO(data_str)
        reader = sizelimit.LimitingReader(data, BYTES)
        res = reader.read()
        self.assertEqual(data_str, res)

    def test_limiting_reader_fails(self):
        BYTES = 1024

        def _consume_all_iter():
            bytes_read = 0
            data = six.StringIO("*" * BYTES)
            for chunk in sizelimit.LimitingReader(data, BYTES - 1):
                bytes_read += len(chunk)

        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          _consume_all_iter)

        def _consume_all_read():
            bytes_read = 0
            data = six.StringIO("*" * BYTES)
            reader = sizelimit.LimitingReader(data, BYTES - 1)
            byte = reader.read(1)
            while len(byte) != 0:
                bytes_read += 1
                byte = reader.read(1)

        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          _consume_all_read)


class TestRequestBodySizeLimiter(test_base.BaseTestCase):

    def setUp(self):
        super(TestRequestBodySizeLimiter, self).setUp()
        self.useFixture(config.Config())

        @webob.dec.wsgify()
        def fake_app(req):
            return webob.Response(req.body)

        self.middleware = sizelimit.RequestBodySizeLimiter(fake_app)
        self.MAX_REQUEST_BODY_SIZE = (
            self.middleware.oslo_conf.oslo_middleware.max_request_body_size)
        self.request = webob.Request.blank('/', method='POST')

    def test_content_length_acceptable(self):
        self.request.headers['Content-Length'] = self.MAX_REQUEST_BODY_SIZE
        self.request.body = b"0" * self.MAX_REQUEST_BODY_SIZE
        response = self.request.get_response(self.middleware)
        self.assertEqual(200, response.status_int)

    def test_content_length_too_large(self):
        self.request.headers['Content-Length'] = self.MAX_REQUEST_BODY_SIZE + 1
        self.request.body = b"0" * (self.MAX_REQUEST_BODY_SIZE + 1)
        response = self.request.get_response(self.middleware)
        self.assertEqual(413, response.status_int)
