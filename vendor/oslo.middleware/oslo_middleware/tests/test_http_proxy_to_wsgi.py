# Copyright (c) 2015 Red Hat, Inc.
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
from wsgiref import util

from oslotest import base as test_base
import webob

from oslo_middleware import http_proxy_to_wsgi


class TestHTTPProxyToWSGI(test_base.BaseTestCase):

    def setUp(self):
        super(TestHTTPProxyToWSGI, self).setUp()

        @webob.dec.wsgify()
        def fake_app(req):
            return util.application_uri(req.environ)

        self.middleware = http_proxy_to_wsgi.HTTPProxyToWSGI(fake_app)
        self.middleware.oslo_conf.set_override('enable_proxy_headers_parsing',
                                               True,
                                               group='oslo_middleware')
        self.request = webob.Request.blank('/foo/bar', method='POST')

    def test_backward_compat(self):
        @webob.dec.wsgify()
        def fake_app(req):
            return util.application_uri(req.environ)

        self.middleware = http_proxy_to_wsgi.HTTPProxyToWSGI(fake_app)
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"http://localhost:80/", response.body)

    def test_no_headers(self):
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"http://localhost:80/", response.body)

    def test_url_translate_ssl(self):
        self.request.headers['X-Forwarded-Proto'] = "https"
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"https://localhost:80/", response.body)

    def test_url_translate_ssl_port(self):
        self.request.headers['X-Forwarded-Proto'] = "https"
        self.request.headers['X-Forwarded-Host'] = "example.com:123"
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"https://example.com:123/", response.body)

    def test_url_translate_host_ipv6(self):
        self.request.headers['X-Forwarded-Proto'] = "https"
        self.request.headers['X-Forwarded-Host'] = "[f00:b4d::1]:123"
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"https://[f00:b4d::1]:123/", response.body)

    def test_url_translate_base(self):
        self.request.headers['X-Forwarded-Prefix'] = "/bla"
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"http://localhost:80/bla", response.body)

    def test_url_translate_port_and_base_and_proto_and_host(self):
        self.request.headers['X-Forwarded-Proto'] = "https"
        self.request.headers['X-Forwarded-Prefix'] = "/bla"
        self.request.headers['X-Forwarded-Host'] = "example.com:8043"
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"https://example.com:8043/bla", response.body)

    def test_rfc7239_invalid(self):
        self.request.headers['Forwarded'] = (
            "iam=anattacker;metoo, I will crash you!!P;m,xx")
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"http://localhost:80/", response.body)

    def test_rfc7239_proto(self):
        self.request.headers['Forwarded'] = (
            "for=foobar;proto=https, for=foobaz;proto=http")
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"https://localhost:80/", response.body)

    def test__parse_rfc7239_header(self):
        expected_result = [{'for': 'foobar', 'proto': 'https'},
                           {'for': 'foobaz', 'proto': 'http'}]

        result = self.middleware._parse_rfc7239_header(
            "for=foobar;proto=https, for=foobaz;proto=http")
        self.assertEqual(expected_result, result)

        result = self.middleware._parse_rfc7239_header(
            "for=foobar; proto=https, for=foobaz; proto=http")
        self.assertEqual(expected_result, result)

    def test_rfc7239_proto_host(self):
        self.request.headers['Forwarded'] = (
            "for=foobar;proto=https;host=example.com, for=foobaz;proto=http")
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"https://example.com/", response.body)

    def test_rfc7239_proto_host_base(self):
        self.request.headers['Forwarded'] = (
            "for=foobar;proto=https;host=example.com:8043, for=foobaz")
        self.request.headers['X-Forwarded-Prefix'] = "/bla"
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"https://example.com:8043/bla", response.body)

    def test_forwarded_for_headers(self):
        @webob.dec.wsgify()
        def fake_app(req):
            return req.environ['REMOTE_ADDR']

        self.middleware = http_proxy_to_wsgi.HTTPProxyToWSGI(fake_app)
        forwarded_for_addr = '1.2.3.4'
        forwarded_addr = '8.8.8.8'

        # If both X-Forwarded-For and Fowarded headers are present, it should
        # use the Forwarded header and ignore the X-Forwarded-For header.
        self.request.headers['Forwarded'] = (
            "for=%s;proto=https;host=example.com:8043" % (forwarded_addr))
        self.request.headers['X-Forwarded-For'] = forwarded_for_addr
        response = self.request.get_response(self.middleware)
        self.assertEqual(forwarded_addr.encode(), response.body)

        # Now if only X-Forwarded-For header is present, it should be used.
        del self.request.headers['Forwarded']
        response = self.request.get_response(self.middleware)
        self.assertEqual(forwarded_for_addr.encode(), response.body)


class TestHTTPProxyToWSGIDisabled(test_base.BaseTestCase):

    def setUp(self):
        super(TestHTTPProxyToWSGIDisabled, self).setUp()

        @webob.dec.wsgify()
        def fake_app(req):
            return util.application_uri(req.environ)

        self.middleware = http_proxy_to_wsgi.HTTPProxyToWSGI(fake_app)
        self.middleware.oslo_conf.set_override('enable_proxy_headers_parsing',
                                               False,
                                               group='oslo_middleware')
        self.request = webob.Request.blank('/foo/bar', method='POST')

    def test_no_headers(self):
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"http://localhost:80/", response.body)

    def test_url_translate_ssl_has_no_effect(self):
        self.request.headers['X-Forwarded-Proto'] = "https"
        self.request.headers['X-Forwarded-Host'] = "example.com:123"
        response = self.request.get_response(self.middleware)
        self.assertEqual(b"http://localhost:80/", response.body)
