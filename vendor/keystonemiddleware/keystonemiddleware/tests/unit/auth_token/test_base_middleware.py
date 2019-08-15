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

from keystoneauth1 import fixture
import mock
import testtools
import webob

from keystonemiddleware import auth_token
from keystonemiddleware.auth_token import _request


class FakeApp(object):

    @webob.dec.wsgify
    def __call__(self, req):
        return webob.Response()


class FetchingMiddleware(auth_token.BaseAuthProtocol):

    def __init__(self, app, token_dict={}, **kwargs):
        super(FetchingMiddleware, self).__init__(app, **kwargs)
        self.token_dict = token_dict

    def fetch_token(self, token, **kwargs):
        try:
            return self.token_dict[token]
        except KeyError:
            raise auth_token.InvalidToken()


class BaseAuthProtocolTests(testtools.TestCase):

    @mock.patch.multiple(auth_token.BaseAuthProtocol,
                         process_request=mock.DEFAULT,
                         process_response=mock.DEFAULT)
    def test_process_flow(self, process_request, process_response):
        m = auth_token.BaseAuthProtocol(FakeApp())

        process_request.return_value = None
        process_response.side_effect = lambda x: x

        req = webob.Request.blank('/', method='GET')
        resp = req.get_response(m)

        self.assertEqual(200, resp.status_code)

        self.assertEqual(1, process_request.call_count)
        self.assertIsInstance(process_request.call_args[0][0],
                              _request._AuthTokenRequest)

        self.assertEqual(1, process_response.call_count)
        self.assertIsInstance(process_response.call_args[0][0], webob.Response)

    @classmethod
    def call(cls, middleware, method='GET', path='/', headers=None):
        req = webob.Request.blank(path)
        req.method = method

        for k, v in (headers or {}).items():
            req.headers[k] = v

        resp = req.get_response(middleware)
        resp.request = req
        return resp

    def test_good_v3_user_token(self):
        t = fixture.V3Token()
        t.set_project_scope()
        role = t.add_role()

        token_id = uuid.uuid4().hex
        token_dict = {token_id: t}

        @webob.dec.wsgify
        def _do_cb(req):
            self.assertEqual(token_id, req.headers['X-Auth-Token'].strip())

            self.assertEqual('Confirmed', req.headers['X-Identity-Status'])
            self.assertNotIn('X-Service-Token', req.headers)

            p = req.environ['keystone.token_auth']

            self.assertTrue(p.has_user_token)
            self.assertFalse(p.has_service_token)

            self.assertEqual(t.project_id, p.user.project_id)
            self.assertEqual(t.project_domain_id, p.user.project_domain_id)
            self.assertEqual(t.user_id, p.user.user_id)
            self.assertEqual(t.user_domain_id, p.user.user_domain_id)
            self.assertIn(role['name'], p.user.role_names)

            return webob.Response()

        m = FetchingMiddleware(_do_cb, token_dict)
        self.call(m, headers={'X-Auth-Token': token_id})

        # also try with whitespace in the token
        self.call(m, headers={'X-Auth-Token': token_id + ' '})
        self.call(m, headers={'X-Auth-Token': token_id + '\r'})

    def test_invalid_user_token(self):
        token_id = uuid.uuid4().hex

        @webob.dec.wsgify
        def _do_cb(req):
            self.assertEqual('Invalid', req.headers['X-Identity-Status'])
            self.assertEqual(token_id, req.headers['X-Auth-Token'])
            return webob.Response()

        m = FetchingMiddleware(_do_cb)
        self.call(m, headers={'X-Auth-Token': token_id})

    def test_expired_user_token(self):
        t = fixture.V3Token()
        t.set_project_scope()
        t.expires = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)

        token_id = uuid.uuid4().hex
        token_dict = {token_id: t}

        @webob.dec.wsgify
        def _do_cb(req):
            self.assertEqual('Invalid', req.headers['X-Identity-Status'])
            self.assertEqual(token_id, req.headers['X-Auth-Token'])
            return webob.Response()

        m = FetchingMiddleware(_do_cb, token_dict=token_dict)
        self.call(m, headers={'X-Auth-Token': token_id})

    def test_good_v3_service_token(self):
        t = fixture.V3Token()
        t.set_project_scope()
        role = t.add_role()

        token_id = uuid.uuid4().hex
        token_dict = {token_id: t}

        @webob.dec.wsgify
        def _do_cb(req):
            self.assertEqual(token_id, req.headers['X-Service-Token'].strip())

            self.assertEqual('Confirmed',
                             req.headers['X-Service-Identity-Status'])
            self.assertNotIn('X-Auth-Token', req.headers)

            p = req.environ['keystone.token_auth']

            self.assertFalse(p.has_user_token)
            self.assertTrue(p.has_service_token)

            self.assertEqual(t.project_id, p.service.project_id)
            self.assertEqual(t.project_domain_id, p.service.project_domain_id)
            self.assertEqual(t.user_id, p.service.user_id)
            self.assertEqual(t.user_domain_id, p.service.user_domain_id)
            self.assertIn(role['name'], p.service.role_names)

            return webob.Response()

        m = FetchingMiddleware(_do_cb, token_dict)
        self.call(m, headers={'X-Service-Token': token_id})

        # also try with whitespace in the token
        self.call(m, headers={'X-Service-Token': token_id + ' '})
        self.call(m, headers={'X-Service-Token': token_id + '\r'})

    def test_invalid_service_token(self):
        token_id = uuid.uuid4().hex

        @webob.dec.wsgify
        def _do_cb(req):
            self.assertEqual('Invalid',
                             req.headers['X-Service-Identity-Status'])
            self.assertEqual(token_id, req.headers['X-Service-Token'])
            return webob.Response()

        m = FetchingMiddleware(_do_cb)
        self.call(m, headers={'X-Service-Token': token_id})

    def test_expired_service_token(self):
        t = fixture.V3Token()
        t.set_project_scope()
        t.expires = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)

        token_id = uuid.uuid4().hex
        token_dict = {token_id: t}

        @webob.dec.wsgify
        def _do_cb(req):
            self.assertEqual('Invalid',
                             req.headers['X-Service-Identity-Status'])
            self.assertEqual(token_id, req.headers['X-Service-Token'])
            return webob.Response()

        m = FetchingMiddleware(_do_cb, token_dict=token_dict)
        self.call(m, headers={'X-Service-Token': token_id})

    def test_base_doesnt_block_project_id(self):
        # X-Project-Id and X-Domain-Id must pass for tokenless/x509 auth
        project_id = uuid.uuid4().hex
        domain_id = uuid.uuid4().hex
        body = uuid.uuid4().hex

        @webob.dec.wsgify
        def _do_cb(req):
            self.assertEqual(project_id, req.headers['X-Project-Id'])
            self.assertEqual(domain_id, req.headers['X-Domain-Id'])
            return webob.Response(body, 200)

        m = FetchingMiddleware(_do_cb)
        resp = self.call(m, headers={'X-Project-Id': project_id,
                                     'X-Domain-Id': domain_id})
        self.assertEqual(body, resp.text)
