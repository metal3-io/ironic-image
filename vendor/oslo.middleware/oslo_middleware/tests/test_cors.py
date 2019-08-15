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

from oslo_config import fixture
from oslotest import base as test_base
import webob
import webob.dec
import webob.exc as exc

from oslo_middleware import cors


@webob.dec.wsgify
def test_application(req):
    if req.path_info == '/server_cors':
        # Mirror back the origin in the request.
        response = webob.Response(status=200)
        response.headers['Access-Control-Allow-Origin'] = \
            req.headers['Origin']
        response.headers['X-Server-Generated-Response'] = '1'
        return response

    if req.path_info == '/server_cors_vary':
        # Mirror back the origin in the request.
        response = webob.Response(status=200)
        response.headers['Vary'] = 'Custom-Vary'
        return response

    if req.path_info == '/server_no_cors':
        # Send a response with no CORS headers.
        response = webob.Response(status=200)
        return response

    if req.method == 'OPTIONS':
        raise exc.HTTPNotFound()

    return 'Hello World'


class CORSTestBase(test_base.BaseTestCase):
    """Base class for all CORS tests.

    Sets up applications and helper methods.
    """

    def setUp(self):
        """Setup the tests."""
        super(CORSTestBase, self).setUp()

        # Set up the config fixture.
        self.config_fixture = self.useFixture(fixture.Config())
        self.config = self.config_fixture.conf

    def assertCORSResponse(self, response,
                           status='200 OK',
                           allow_origin=None,
                           max_age=None,
                           allow_methods=None,
                           allow_headers=None,
                           allow_credentials=None,
                           expose_headers=None,
                           vary='Origin',
                           has_content_type=False):
        """Test helper for CORS response headers.

        Assert all the headers in a given response. By default, we assume
        the response is empty.
        """

        # Assert response status.
        self.assertEqual(status, response.status)

        # Assert the Access-Control-Allow-Origin header.
        self.assertHeader(response,
                          'Access-Control-Allow-Origin',
                          allow_origin)

        # Assert the Access-Control-Max-Age header.
        self.assertHeader(response,
                          'Access-Control-Max-Age',
                          max_age)

        # Assert the Access-Control-Allow-Methods header.
        self.assertHeader(response,
                          'Access-Control-Allow-Methods',
                          allow_methods)

        # Assert the Access-Control-Allow-Headers header.
        self.assertHeader(response,
                          'Access-Control-Allow-Headers',
                          allow_headers)

        # Assert the Access-Control-Allow-Credentials header.
        self.assertHeader(response,
                          'Access-Control-Allow-Credentials',
                          allow_credentials)

        # Assert the Access-Control-Expose-Headers header.
        self.assertHeader(response,
                          'Access-Control-Expose-Headers',
                          expose_headers)

        # Assert no Content-Type added.
        if not has_content_type:
            self.assertHeader(response, 'Content-Type')

        # If we're expecting an origin response, also assert that the
        # Vary: Origin header is set, since this implementation of the CORS
        # specification permits multiple origin domains.
        if allow_origin:
            self.assertHeader(response, 'Vary', vary)

    def assertHeader(self, response, header, value=None):
        if value:
            self.assertIn(header, response.headers)
            self.assertEqual(str(value),
                             response.headers[header])
        else:
            self.assertNotIn(header, response.headers)


class CORSTestDefaultOverrides(CORSTestBase):
    def setUp(self):
        super(CORSTestDefaultOverrides, self).setUp()

        fixture = self.config_fixture  # Line length accommodation

        fixture.load_raw_values(group='cors',
                                allowed_origin='http://valid.example.com')

        fixture.load_raw_values(group='cors.override_creds',
                                allowed_origin='http://creds.example.com',
                                allow_credentials='True')

        fixture.load_raw_values(group='cors.override_headers',
                                allowed_origin='http://headers.example.com',
                                expose_headers='X-Header-1,X-Header-2',
                                allow_headers='X-Header-1,X-Header-2')

        self.override_opts = {
            'expose_headers': ['X-Header-1'],
            'allow_headers': ['X-Header-2'],
            'allow_methods': ['GET', 'DELETE'],
            'allow_credentials': False,
            'max_age': 10
        }

    def test_config_defaults(self):
        """Assert that using set_defaults overrides the appropriate values."""

        cors.set_defaults(**self.override_opts)

        for opt in cors.CORS_OPTS:
            if opt.dest in self.override_opts:
                self.assertEqual(self.override_opts[opt.dest], opt.default)

    def test_invalid_default_option(self):
        """Assert that using set_defaults only permits valid options."""

        self.assertRaises(AttributeError,
                          cors.set_defaults,
                          allowed_origin='test')

    def test_cascading_override(self):
        """Assert that using set_defaults overrides cors.* config values."""

        # set defaults
        cors.set_defaults(**self.override_opts)

        # Now that the config is set up, create our application.
        self.application = cors.CORS(test_application, self.config)

        # Check the global configuration for expected values:
        gc = self.config.cors
        self.assertEqual(['http://valid.example.com'], gc.allowed_origin)
        self.assertEqual(self.override_opts['allow_credentials'],
                         gc.allow_credentials)
        self.assertEqual(self.override_opts['expose_headers'],
                         gc.expose_headers)
        self.assertEqual(10, gc.max_age)
        self.assertEqual(self.override_opts['allow_methods'],
                         gc.allow_methods)
        self.assertEqual(self.override_opts['allow_headers'],
                         gc.allow_headers)

        # Check the child configuration for expected values:
        cc = self.config['cors.override_creds']
        self.assertEqual(['http://creds.example.com'], cc.allowed_origin)
        self.assertTrue(cc.allow_credentials)
        self.assertEqual(self.override_opts['expose_headers'],
                         cc.expose_headers)
        self.assertEqual(10, cc.max_age)
        self.assertEqual(self.override_opts['allow_methods'],
                         cc.allow_methods)
        self.assertEqual(self.override_opts['allow_headers'],
                         cc.allow_headers)

        # Check the other child configuration for expected values:
        ec = self.config['cors.override_headers']
        self.assertEqual(['http://headers.example.com'], ec.allowed_origin)
        self.assertEqual(self.override_opts['allow_credentials'],
                         ec.allow_credentials)
        self.assertEqual(['X-Header-1', 'X-Header-2'], ec.expose_headers)
        self.assertEqual(10, ec.max_age)
        self.assertEqual(self.override_opts['allow_methods'],
                         ec.allow_methods)
        self.assertEqual(['X-Header-1', 'X-Header-2'], ec.allow_headers)


class CORSTestFilterFactory(CORSTestBase):
    """Test the CORS filter_factory method."""

    def test_filter_factory(self):
        self.config([])

        # Test a valid filter.
        filter = cors.filter_factory(None,
                                     allowed_origin='http://valid.example.com',
                                     allow_credentials='False',
                                     max_age='',
                                     expose_headers='',
                                     allow_methods='GET',
                                     allow_headers='')
        application = filter(test_application)

        self.assertIn('http://valid.example.com', application.allowed_origins)

        config = application.allowed_origins['http://valid.example.com']
        self.assertEqual(False, config['allow_credentials'])
        self.assertIsNone(config['max_age'])
        self.assertEqual([], config['expose_headers'])
        self.assertEqual(['GET'], config['allow_methods'])
        self.assertEqual([], config['allow_headers'])

    def test_filter_factory_multiorigin(self):
        self.config([])

        # Test a valid filter.
        filter = cors.filter_factory(None,
                                     allowed_origin='http://valid.example.com,'
                                                    'http://other.example.com')
        application = filter(test_application)

        self.assertIn('http://valid.example.com', application.allowed_origins)
        self.assertIn('http://other.example.com', application.allowed_origins)

    def test_no_origin_fail(self):
        '''Assert that a filter factory with no allowed_origin fails.'''
        self.assertRaises(TypeError,
                          cors.filter_factory,
                          global_conf=None,
                          # allowed_origin=None,  # Expected value.
                          allow_credentials='False',
                          max_age='',
                          expose_headers='',
                          allow_methods='GET',
                          allow_headers='')

    def test_no_origin_but_oslo_config_project(self):
        '''Assert that a filter factory with oslo_config_project succeed.'''
        cors.filter_factory(global_conf=None, oslo_config_project='foobar')

    def test_cor_config_sections_with_defaults(self):
        '''Assert cors.* config sections with default values work.'''

        # Set up the config fixture.
        self.config_fixture.load_raw_values(group='cors.subdomain')

        # Now that the config is set up, create our application.
        self.application = cors.CORS(test_application, self.config)


class CORSRegularRequestTest(CORSTestBase):
    """CORS Specification Section 6.1

    http://www.w3.org/TR/cors/#resource-requests
    """

    # List of HTTP methods (other than OPTIONS) to test with.
    methods = ['POST', 'PUT', 'DELETE', 'GET', 'TRACE', 'HEAD']

    def setUp(self):
        """Setup the tests."""
        super(CORSRegularRequestTest, self).setUp()

        fixture = self.config_fixture  # Line length accommodation
        fixture.load_raw_values(group='cors',
                                allowed_origin='http://valid.example.com',
                                allow_credentials='False',
                                max_age='',
                                expose_headers='',
                                allow_methods='GET',
                                allow_headers='')

        fixture.load_raw_values(group='cors.credentials',
                                allowed_origin='http://creds.example.com',
                                allow_credentials='True')

        fixture.load_raw_values(group='cors.exposed-headers',
                                allowed_origin='http://headers.example.com',
                                expose_headers='X-Header-1,X-Header-2',
                                allow_headers='X-Header-1,X-Header-2')

        fixture.load_raw_values(group='cors.cached',
                                allowed_origin='http://cached.example.com',
                                max_age='3600')

        fixture.load_raw_values(group='cors.get-only',
                                allowed_origin='http://get.example.com',
                                allow_methods='GET')
        fixture.load_raw_values(group='cors.all-methods',
                                allowed_origin='http://all.example.com',
                                allow_methods='GET,PUT,POST,DELETE,HEAD')

        fixture.load_raw_values(group='cors.duplicate',
                                allowed_origin='http://domain1.example.com,'
                                               'http://domain2.example.com')

        # Now that the config is set up, create our application.
        self.application = cors.CORS(test_application, self.config)

    def test_config_overrides(self):
        """Assert that the configuration options are properly registered."""

        # Confirm global configuration
        gc = self.config.cors
        self.assertEqual(['http://valid.example.com'], gc.allowed_origin)
        self.assertEqual(False, gc.allow_credentials)
        self.assertEqual([], gc.expose_headers)
        self.assertIsNone(gc.max_age)
        self.assertEqual(['GET'], gc.allow_methods)
        self.assertEqual([], gc.allow_headers)

        # Confirm credentials overrides.
        cc = self.config['cors.credentials']
        self.assertEqual(['http://creds.example.com'], cc.allowed_origin)
        self.assertEqual(True, cc.allow_credentials)
        self.assertEqual(gc.expose_headers, cc.expose_headers)
        self.assertEqual(gc.max_age, cc.max_age)
        self.assertEqual(gc.allow_methods, cc.allow_methods)
        self.assertEqual(gc.allow_headers, cc.allow_headers)

        # Confirm exposed-headers overrides.
        ec = self.config['cors.exposed-headers']
        self.assertEqual(['http://headers.example.com'], ec.allowed_origin)
        self.assertEqual(gc.allow_credentials, ec.allow_credentials)
        self.assertEqual(['X-Header-1', 'X-Header-2'], ec.expose_headers)
        self.assertEqual(gc.max_age, ec.max_age)
        self.assertEqual(gc.allow_methods, ec.allow_methods)
        self.assertEqual(['X-Header-1', 'X-Header-2'], ec.allow_headers)

        # Confirm cached overrides.
        chc = self.config['cors.cached']
        self.assertEqual(['http://cached.example.com'], chc.allowed_origin)
        self.assertEqual(gc.allow_credentials, chc.allow_credentials)
        self.assertEqual(gc.expose_headers, chc.expose_headers)
        self.assertEqual(3600, chc.max_age)
        self.assertEqual(gc.allow_methods, chc.allow_methods)
        self.assertEqual(gc.allow_headers, chc.allow_headers)

        # Confirm get-only overrides.
        goc = self.config['cors.get-only']
        self.assertEqual(['http://get.example.com'], goc.allowed_origin)
        self.assertEqual(gc.allow_credentials, goc.allow_credentials)
        self.assertEqual(gc.expose_headers, goc.expose_headers)
        self.assertEqual(gc.max_age, goc.max_age)
        self.assertEqual(['GET'], goc.allow_methods)
        self.assertEqual(gc.allow_headers, goc.allow_headers)

        # Confirm all-methods overrides.
        ac = self.config['cors.all-methods']
        self.assertEqual(['http://all.example.com'], ac.allowed_origin)
        self.assertEqual(gc.allow_credentials, ac.allow_credentials)
        self.assertEqual(gc.expose_headers, ac.expose_headers)
        self.assertEqual(gc.max_age, ac.max_age)
        self.assertEqual(['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                         ac.allow_methods)
        self.assertEqual(gc.allow_headers, ac.allow_headers)

        # Confirm duplicate domains.
        ac = self.config['cors.duplicate']
        self.assertEqual(['http://domain1.example.com',
                          'http://domain2.example.com'],
                         ac.allowed_origin)
        self.assertEqual(gc.allow_credentials, ac.allow_credentials)
        self.assertEqual(gc.expose_headers, ac.expose_headers)
        self.assertEqual(gc.max_age, ac.max_age)
        self.assertEqual(gc.allow_methods, ac.allow_methods)
        self.assertEqual(gc.allow_headers, ac.allow_headers)

    def test_no_origin_header(self):
        """CORS Specification Section 6.1.1

        If the Origin header is not present terminate this set of steps. The
        request is outside the scope of this specification.
        """
        for method in self.methods:
            request = webob.Request.blank('/')
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None,
                                    has_content_type=True)

    def test_origin_headers(self):
        """CORS Specification Section 6.1.2

        If the value of the Origin header is not a case-sensitive match for
        any of the values in list of origins, do not set any additional
        headers and terminate this set of steps.
        """

        # Test valid origin header.
        for method in self.methods:
            request = webob.Request.blank('/')
            request.method = method
            request.headers['Origin'] = 'http://valid.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://valid.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None,
                                    has_content_type=True)

        # Test origin header not present in configuration.
        for method in self.methods:
            request = webob.Request.blank('/')
            request.method = method
            request.headers['Origin'] = 'http://invalid.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None,
                                    has_content_type=True)

        # Test valid, but case-mismatched origin header.
        for method in self.methods:
            request = webob.Request.blank('/')
            request.method = method
            request.headers['Origin'] = 'http://VALID.EXAMPLE.COM'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None,
                                    has_content_type=True)

        # Test valid header from list of duplicates.
        for method in self.methods:
            request = webob.Request.blank('/')
            request.method = method
            request.headers['Origin'] = 'http://domain2.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://domain2.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None,
                                    has_content_type=True)

    def test_supports_credentials(self):
        """CORS Specification Section 6.1.3

        If the resource supports credentials add a single
        Access-Control-Allow-Origin header, with the value of the Origin header
        as value, and add a single Access-Control-Allow-Credentials header with
        the case-sensitive string "true" as value.

        Otherwise, add a single Access-Control-Allow-Origin header, with
        either the value of the Origin header or the string "*" as value.

        NOTE: We never use the "*" as origin.
        """
        # Test valid origin header without credentials.
        for method in self.methods:
            request = webob.Request.blank('/')
            request.method = method
            request.headers['Origin'] = 'http://valid.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://valid.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None,
                                    has_content_type=True)

        # Test valid origin header with credentials
        for method in self.methods:
            request = webob.Request.blank('/')
            request.method = method
            request.headers['Origin'] = 'http://creds.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://creds.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials="true",
                                    expose_headers=None,
                                    has_content_type=True)

    def test_expose_headers(self):
        """CORS Specification Section 6.1.4

        If the list of exposed headers is not empty add one or more
        Access-Control-Expose-Headers headers, with as values the header field
        names given in the list of exposed headers.
        """
        for method in self.methods:
            request = webob.Request.blank('/')
            request.method = method
            request.headers['Origin'] = 'http://headers.example.com'
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://headers.example.com',
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers='X-Header-1,X-Header-2',
                                    has_content_type=True)

    def test_application_options_response(self):
        """Assert that an application provided OPTIONS response is honored.

        If the underlying application, via middleware or other, provides a
        CORS response, its response should be honored.
        """
        test_origin = 'http://creds.example.com'

        request = webob.Request.blank('/server_cors')
        request.method = "GET"
        request.headers['Origin'] = test_origin
        request.headers['Access-Control-Request-Method'] = 'GET'

        response = request.get_response(self.application)

        # If the regular CORS handling catches this request, it should set
        # the allow credentials header. This makes sure that it doesn't.
        self.assertNotIn('Access-Control-Allow-Credentials', response.headers)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'],
                         test_origin)
        self.assertEqual(response.headers['X-Server-Generated-Response'],
                         '1')

    def test_application_vary_respected(self):
        """Assert that an application's provided Vary header is persisted.

        If the underlying application, via middleware or other, provides a
        Vary header, its response should be honored.
        """

        request = webob.Request.blank('/server_cors_vary')
        request.method = "GET"
        request.headers['Origin'] = 'http://valid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'

        response = request.get_response(self.application)

        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://valid.example.com',
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None,
                                vary='Custom-Vary,Origin',
                                has_content_type=True)


class CORSPreflightRequestTest(CORSTestBase):
    """CORS Specification Section 6.2

    http://www.w3.org/TR/cors/#resource-preflight-requests
    """

    def setUp(self):
        super(CORSPreflightRequestTest, self).setUp()

        fixture = self.config_fixture  # Line length accommodation
        fixture.load_raw_values(group='cors',
                                allowed_origin='http://valid.example.com',
                                allow_credentials='False',
                                max_age='',
                                expose_headers='',
                                allow_methods='GET',
                                allow_headers='')

        fixture.load_raw_values(group='cors.credentials',
                                allowed_origin='http://creds.example.com',
                                allow_credentials='True')

        fixture.load_raw_values(group='cors.exposed-headers',
                                allowed_origin='http://headers.example.com',
                                expose_headers='X-Header-1,X-Header-2',
                                allow_headers='X-Header-1,X-Header-2')

        fixture.load_raw_values(group='cors.cached',
                                allowed_origin='http://cached.example.com',
                                max_age='3600')

        fixture.load_raw_values(group='cors.get-only',
                                allowed_origin='http://get.example.com',
                                allow_methods='GET')
        fixture.load_raw_values(group='cors.all-methods',
                                allowed_origin='http://all.example.com',
                                allow_methods='GET,PUT,POST,DELETE,HEAD')

        # Now that the config is set up, create our application.
        self.application = cors.CORS(test_application, self.config)

    def test_config_overrides(self):
        """Assert that the configuration options are properly registered."""

        # Confirm global configuration
        gc = self.config.cors
        self.assertEqual(gc.allowed_origin, ['http://valid.example.com'])
        self.assertEqual(gc.allow_credentials, False)
        self.assertEqual(gc.expose_headers, [])
        self.assertIsNone(gc.max_age)
        self.assertEqual(gc.allow_methods, ['GET'])
        self.assertEqual(gc.allow_headers, [])

        # Confirm credentials overrides.
        cc = self.config['cors.credentials']
        self.assertEqual(['http://creds.example.com'], cc.allowed_origin)
        self.assertEqual(True, cc.allow_credentials)
        self.assertEqual(gc.expose_headers, cc.expose_headers)
        self.assertEqual(gc.max_age, cc.max_age)
        self.assertEqual(gc.allow_methods, cc.allow_methods)
        self.assertEqual(gc.allow_headers, cc.allow_headers)

        # Confirm exposed-headers overrides.
        ec = self.config['cors.exposed-headers']
        self.assertEqual(['http://headers.example.com'], ec.allowed_origin)
        self.assertEqual(gc.allow_credentials, ec.allow_credentials)
        self.assertEqual(['X-Header-1', 'X-Header-2'], ec.expose_headers)
        self.assertEqual(gc.max_age, ec.max_age)
        self.assertEqual(gc.allow_methods, ec.allow_methods)
        self.assertEqual(['X-Header-1', 'X-Header-2'], ec.allow_headers)

        # Confirm cached overrides.
        chc = self.config['cors.cached']
        self.assertEqual(['http://cached.example.com'], chc.allowed_origin)
        self.assertEqual(gc.allow_credentials, chc.allow_credentials)
        self.assertEqual(gc.expose_headers, chc.expose_headers)
        self.assertEqual(3600, chc.max_age)
        self.assertEqual(gc.allow_methods, chc.allow_methods)
        self.assertEqual(gc.allow_headers, chc.allow_headers)

        # Confirm get-only overrides.
        goc = self.config['cors.get-only']
        self.assertEqual(['http://get.example.com'], goc.allowed_origin)
        self.assertEqual(gc.allow_credentials, goc.allow_credentials)
        self.assertEqual(gc.expose_headers, goc.expose_headers)
        self.assertEqual(gc.max_age, goc.max_age)
        self.assertEqual(['GET'], goc.allow_methods)
        self.assertEqual(gc.allow_headers, goc.allow_headers)

        # Confirm all-methods overrides.
        ac = self.config['cors.all-methods']
        self.assertEqual(['http://all.example.com'], ac.allowed_origin)
        self.assertEqual(gc.allow_credentials, ac.allow_credentials)
        self.assertEqual(gc.expose_headers, ac.expose_headers)
        self.assertEqual(gc.max_age, ac.max_age)
        self.assertEqual(ac.allow_methods,
                         ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'])
        self.assertEqual(gc.allow_headers, ac.allow_headers)

    def test_no_origin_header(self):
        """CORS Specification Section 6.2.1

        If the Origin header is not present terminate this set of steps. The
        request is outside the scope of this specification.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_case_sensitive_origin(self):
        """CORS Specification Section 6.2.2

        If the value of the Origin header is not a case-sensitive match for
        any of the values in list of origins do not set any additional headers
        and terminate this set of steps.
        """

        # Test valid domain
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://valid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://valid.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='',
                                allow_credentials=None,
                                expose_headers=None)

        # Test invalid domain
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://invalid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

        # Test case-sensitive mismatch domain
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://VALID.EXAMPLE.COM'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_simple_header_response(self):
        """CORS Specification Section 3

        A header is said to be a simple header if the header field name is an
        ASCII case-insensitive match for Accept, Accept-Language, or
        Content-Language or if it is an ASCII case-insensitive match for
        Content-Type and the header field value media type (excluding
        parameters) is an ASCII case-insensitive match for
        application/x-www-form-urlencoded, multipart/form-data, or text/plain.

        NOTE: We are not testing the media type cases.
        """

        simple_headers = ','.join([
            'accept',
            'accept-language',
            'content-language',
            'content-type'
        ])

        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://valid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = simple_headers
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://valid.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=simple_headers,
                                allow_credentials=None,
                                expose_headers=None)

    def test_no_request_method(self):
        """CORS Specification Section 6.2.3

        If there is no Access-Control-Request-Method header or if parsing
        failed, do not set any additional headers and terminate this set of
        steps. The request is outside the scope of this specification.
        """

        # Test valid domain, valid method.
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://get.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://get.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

        # Test valid domain, invalid HTTP method.
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://valid.example.com'
        request.headers['Access-Control-Request-Method'] = 'TEAPOT'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

        # Test valid domain, no HTTP method.
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://valid.example.com'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_invalid_method(self):
        """CORS Specification Section 6.2.3

        If method is not a case-sensitive match for any of the values in
        list of methods do not set any additional headers and terminate this
        set of steps.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://get.example.com'
        request.headers['Access-Control-Request-Method'] = 'get'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_no_parse_request_headers(self):
        """CORS Specification Section 6.2.4

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.

        If parsing failed do not set any additional headers and terminate
        this set of steps. The request is outside the scope of this
        specification.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = 'value with spaces'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_no_request_headers(self):
        """CORS Specification Section 6.2.4

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = ''
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://headers.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_request_headers(self):
        """CORS Specification Section 6.2.4

        Let header field-names be the values as result of parsing the
        Access-Control-Request-Headers headers.

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = 'X-Header-1,' \
                                                            'X-Header-2'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://headers.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='X-Header-1,X-Header-2',
                                allow_credentials=None,
                                expose_headers=None)

    def test_request_headers_not_permitted(self):
        """CORS Specification Section 6.2.4, 6.2.6

        If there are no Access-Control-Request-Headers headers let header
        field-names be the empty list.

        If any of the header field-names is not a ASCII case-insensitive
        match for any of the values in list of headers do not set any
        additional headers and terminate this set of steps.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = 'X-Not-Exposed,' \
                                                            'X-Never-Exposed'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin=None,
                                max_age=None,
                                allow_methods=None,
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_credentials(self):
        """CORS Specification Section 6.2.7

        If the resource supports credentials add a single
        Access-Control-Allow-Origin header, with the value of the Origin header
        as value, and add a single Access-Control-Allow-Credentials header with
        the case-sensitive string "true" as value.

        Otherwise, add a single Access-Control-Allow-Origin header, with either
        the value of the Origin header or the string "*" as value.

        NOTE: We never use the "*" as origin.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://creds.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://creds.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials="true",
                                expose_headers=None)

    def test_optional_max_age(self):
        """CORS Specification Section 6.2.8

        Optionally add a single Access-Control-Max-Age header with as value
        the amount of seconds the user agent is allowed to cache the result of
        the request.
        """
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://cached.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://cached.example.com',
                                max_age=3600,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None)

    def test_allow_methods(self):
        """CORS Specification Section 6.2.9

        Add one or more Access-Control-Allow-Methods headers consisting of
        (a subset of) the list of methods.

        Since the list of methods can be unbounded, simply returning the method
        indicated by Access-Control-Request-Method (if supported) can be
        enough.
        """
        for method in ['GET', 'PUT', 'POST', 'DELETE']:
            request = webob.Request.blank('/')
            request.method = "OPTIONS"
            request.headers['Origin'] = 'http://all.example.com'
            request.headers['Access-Control-Request-Method'] = method
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin='http://all.example.com',
                                    max_age=None,
                                    allow_methods=method,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

        for method in ['PUT', 'POST', 'DELETE']:
            request = webob.Request.blank('/')
            request.method = "OPTIONS"
            request.headers['Origin'] = 'http://get.example.com'
            request.headers['Access-Control-Request-Method'] = method
            response = request.get_response(self.application)
            self.assertCORSResponse(response,
                                    status='200 OK',
                                    allow_origin=None,
                                    max_age=None,
                                    allow_methods=None,
                                    allow_headers=None,
                                    allow_credentials=None,
                                    expose_headers=None)

    def test_allow_headers(self):
        """CORS Specification Section 6.2.10

        Add one or more Access-Control-Allow-Headers headers consisting of
        (a subset of) the list of headers.

        If each of the header field-names is a simple header and none is
        Content-Type, this step may be skipped.

        If a header field name is a simple header and is not Content-Type, it
        is not required to be listed. Content-Type is to be listed as only a
        subset of its values makes it qualify as simple header.
        """

        requested_headers = 'Content-Type,X-Header-1,Cache-Control,Expires,' \
                            'Last-Modified,Pragma'

        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://headers.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        request.headers['Access-Control-Request-Headers'] = requested_headers
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://headers.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=requested_headers,
                                allow_credentials=None,
                                expose_headers=None)

    def test_application_options_response(self):
        """Assert that an application provided OPTIONS response is honored.

        If the underlying application, via middleware or other, provides a
        CORS response, its response should be honored.
        """
        test_origin = 'http://creds.example.com'

        request = webob.Request.blank('/server_cors')
        request.method = "OPTIONS"
        request.headers['Origin'] = test_origin
        request.headers['Access-Control-Request-Method'] = 'GET'

        response = request.get_response(self.application)

        # If the regular CORS handling catches this request, it should set
        # the allow credentials header. This makes sure that it doesn't.
        self.assertNotIn('Access-Control-Allow-Credentials', response.headers)
        self.assertEqual(test_origin,
                         response.headers['Access-Control-Allow-Origin'])
        self.assertEqual('1',
                         response.headers['X-Server-Generated-Response'])

        # If the application returns an OPTIONS response without CORS
        # headers, assert that we apply headers.
        request = webob.Request.blank('/server_no_cors')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://get.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://get.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers=None,
                                allow_credentials=None,
                                expose_headers=None,
                                has_content_type=True)


class CORSTestWildcard(CORSTestBase):
    """Test the CORS wildcard specification."""

    def setUp(self):
        super(CORSTestWildcard, self).setUp()

        fixture = self.config_fixture  # Line length accommodation
        fixture.load_raw_values(group='cors',
                                allowed_origin='http://default.example.com',
                                allow_credentials='True',
                                max_age='',
                                expose_headers='',
                                allow_methods='GET,PUT,POST,DELETE,HEAD',
                                allow_headers='')

        fixture.load_raw_values(group='cors.wildcard',
                                allowed_origin='*',
                                allow_methods='GET')

        # Now that the config is set up, create our application.
        self.application = cors.CORS(test_application, self.config)

    def test_config_overrides(self):
        """Assert that the configuration options are properly registered."""

        # Confirm global configuration
        gc = self.config.cors
        self.assertEqual(['http://default.example.com'], gc.allowed_origin)
        self.assertEqual(True, gc.allow_credentials)
        self.assertEqual([], gc.expose_headers)
        self.assertIsNone(gc.max_age)
        self.assertEqual(['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                         gc.allow_methods)
        self.assertEqual([], gc.allow_headers)

        # Confirm all-methods overrides.
        ac = self.config['cors.wildcard']
        self.assertEqual(['*'], ac.allowed_origin)
        self.assertEqual(True, gc.allow_credentials)
        self.assertEqual(gc.expose_headers, ac.expose_headers)
        self.assertEqual(gc.max_age, ac.max_age)
        self.assertEqual(['GET'], ac.allow_methods)
        self.assertEqual(gc.allow_headers, ac.allow_headers)

    def test_wildcard_domain(self):
        """CORS Specification, Wildcards

        If the configuration file specifies CORS settings for the wildcard '*'
        domain, it should return those for all origin domains except for the
        overrides.
        """

        # Test valid domain
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://default.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://default.example.com',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='',
                                allow_credentials='true',
                                expose_headers=None)

        # Test valid domain
        request = webob.Request.blank('/')
        request.method = "GET"
        request.headers['Origin'] = 'http://default.example.com'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='http://default.example.com',
                                max_age=None,
                                allow_headers='',
                                allow_credentials='true',
                                expose_headers=None,
                                has_content_type=True)

        # Test invalid domain
        request = webob.Request.blank('/')
        request.method = "OPTIONS"
        request.headers['Origin'] = 'http://invalid.example.com'
        request.headers['Access-Control-Request-Method'] = 'GET'
        response = request.get_response(self.application)
        self.assertCORSResponse(response,
                                status='200 OK',
                                allow_origin='*',
                                max_age=None,
                                allow_methods='GET',
                                allow_headers='',
                                allow_credentials='true',
                                expose_headers=None,
                                has_content_type=True)
