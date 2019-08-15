# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import webob

from oslo_middleware.base import ConfigurableMiddleware
from oslo_middleware.base import Middleware
from oslotest.base import BaseTestCase


@webob.dec.wsgify
def application(req):
    return 'Hello, World!!!'


class TestBase(BaseTestCase):
    """Test the base middleware class."""

    def test_extend_with_request(self):
        """Assert that a newer middleware behaves as appropriate.

        This tests makes sure that the request is passed to the
        middleware's implementation.
        """
        # Bootstrap the application
        self.application = RequestBase(application)

        # Send a request through.
        request = webob.Request({}, method='GET')
        request.get_response(self.application)

        self.assertTrue(self.application.called_with_request)

    def test_extend_without_request(self):
        """Assert that an older middleware behaves as appropriate.

        This tests makes sure that the request method is NOT passed to the
        middleware's implementation, and that there are no other expected
        errors.
        """
        # Bootstrap the application
        self.application = NoRequestBase(application)

        # Send a request through.
        request = webob.Request({}, method='GET')
        request.get_response(self.application)

        self.assertTrue(self.application.called_without_request)

    def test_no_content_type_added(self):
        class TestMiddleware(Middleware):
            @staticmethod
            def process_request(req):
                return "foobar"

        m = TestMiddleware(None)
        request = webob.Request({}, method='GET')
        response = request.get_response(m)
        self.assertNotIn('Content-Type', response.headers)

    def test_paste_deploy_legacy(self):
        app = LegacyMiddlewareTest.factory(
            {'global': True}, local=True)(application)
        self.assertEqual({}, app.conf)

    def test_paste_deploy_configurable(self):
        app = ConfigurableMiddlewareTest.factory(
            {'global': True}, local=True)(application)
        self.assertEqual({'global': True, 'local': True}, app.conf)


class NoRequestBase(Middleware):
    """Test middleware, implements old model."""
    def process_response(self, response):
        self.called_without_request = True
        return response


class RequestBase(Middleware):
    """Test middleware, implements new model."""
    def process_response(self, response, request):
        self.called_with_request = True
        return response


class ConfigurableMiddlewareTest(ConfigurableMiddleware):
    pass


class LegacyMiddlewareTest(Middleware):
    pass
