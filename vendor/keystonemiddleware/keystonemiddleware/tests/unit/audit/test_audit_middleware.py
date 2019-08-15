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

import uuid

import fixtures
import mock
import webob

from keystonemiddleware.tests.unit.audit import base


class AuditMiddlewareTest(base.BaseAuditMiddlewareTest):

    def setUp(self):
        self.notifier = mock.MagicMock()

        p = 'keystonemiddleware.audit._notifier.create_notifier'
        f = fixtures.MockPatch(p, return_value=self.notifier)
        self.notifier_fixture = self.useFixture(f)

        super(AuditMiddlewareTest, self).setUp()

    def test_api_request(self):
        self.create_simple_app().get('/foo/bar',
                                     extra_environ=self.get_environ_header())

        # Check first notification with only 'request'
        call_args = self.notifier.notify.call_args_list[0][0]
        self.assertEqual('audit.http.request', call_args[1])
        self.assertEqual('/foo/bar', call_args[2]['requestPath'])
        self.assertEqual('pending', call_args[2]['outcome'])
        self.assertNotIn('reason', call_args[2])
        self.assertNotIn('reporterchain', call_args[2])

        # Check second notification with request + response
        call_args = self.notifier.notify.call_args_list[1][0]
        self.assertEqual('audit.http.response', call_args[1])
        self.assertEqual('/foo/bar', call_args[2]['requestPath'])
        self.assertEqual('success', call_args[2]['outcome'])
        self.assertIn('reason', call_args[2])
        self.assertIn('reporterchain', call_args[2])

    def test_api_request_failure(self):

        class CustomException(Exception):
            pass

        def cb(req):
            raise CustomException('It happens!')

        try:
            self.create_app(cb).get('/foo/bar',
                                    extra_environ=self.get_environ_header())

            self.fail('Application exception has not been re-raised')
        except CustomException:
            pass

        # Check first notification with only 'request'
        call_args = self.notifier.notify.call_args_list[0][0]
        self.assertEqual('audit.http.request', call_args[1])
        self.assertEqual('/foo/bar', call_args[2]['requestPath'])
        self.assertEqual('pending', call_args[2]['outcome'])
        self.assertNotIn('reporterchain', call_args[2])

        # Check second notification with request + response
        call_args = self.notifier.notify.call_args_list[1][0]
        self.assertEqual('audit.http.response', call_args[1])
        self.assertEqual('/foo/bar', call_args[2]['requestPath'])
        self.assertEqual('unknown', call_args[2]['outcome'])
        self.assertIn('reporterchain', call_args[2])

    def test_process_request_fail(self):
        req = webob.Request.blank('/foo/bar',
                                  environ=self.get_environ_header('GET'))
        req.environ['audit.context'] = {}

        self.create_simple_middleware()._process_request(req)
        self.assertTrue(self.notifier.notify.called)

    def test_process_response_fail(self):
        req = webob.Request.blank('/foo/bar',
                                  environ=self.get_environ_header('GET'))
        req.environ['audit.context'] = {}

        middleware = self.create_simple_middleware()
        middleware._process_response(req, webob.response.Response())
        self.assertTrue(self.notifier.notify.called)

    def test_ignore_req_opt(self):
        app = self.create_simple_app(ignore_req_list='get, PUT')

        # Check GET/PUT request does not send notification
        app.get('/skip/foo', extra_environ=self.get_environ_header())
        app.put('/skip/foo', extra_environ=self.get_environ_header())

        self.assertFalse(self.notifier.notify.called)

        # Check non-GET/PUT request does send notification
        app.post('/accept/foo', extra_environ=self.get_environ_header())

        self.assertEqual(2, self.notifier.notify.call_count)

        call_args = self.notifier.notify.call_args_list[0][0]
        self.assertEqual('audit.http.request', call_args[1])
        self.assertEqual('/accept/foo', call_args[2]['requestPath'])

        call_args = self.notifier.notify.call_args_list[1][0]
        self.assertEqual('audit.http.response', call_args[1])
        self.assertEqual('/accept/foo', call_args[2]['requestPath'])

    def test_cadf_event_context_scoped(self):
        self.create_simple_app().get('/foo/bar',
                                     extra_environ=self.get_environ_header())

        self.assertEqual(2, self.notifier.notify.call_count)
        first, second = [a[0] for a in self.notifier.notify.call_args_list]

        # the Context is the first argument. Let's verify it.
        self.assertIsInstance(first[0], dict)

        # ensure exact same context is used between request and response
        self.assertIs(first[0], second[0])

    def test_cadf_event_scoped_to_request(self):
        app = self.create_simple_app()
        resp = app.get('/foo/bar', extra_environ=self.get_environ_header())
        self.assertIsNotNone(resp.request.environ.get('cadf_event'))

        # ensure exact same event is used between request and response
        self.assertEqual(self.notifier.calls[0].payload['id'],
                         self.notifier.calls[1].payload['id'])

    def test_cadf_event_scoped_to_request_on_error(self):
        middleware = self.create_simple_middleware()

        req = webob.Request.blank('/foo/bar',
                                  environ=self.get_environ_header('GET'))
        req.environ['audit.context'] = {}
        self.notifier.notify.side_effect = Exception('error')

        middleware(req)
        self.assertTrue(self.notifier.notify.called)

        req2 = webob.Request.blank('/foo/bar',
                                   environ=self.get_environ_header('GET'))
        req2.environ['audit.context'] = {}
        self.notifier.reset_mock()

        middleware._process_response(req2, webob.response.Response())
        self.assertTrue(self.notifier.notify.called)
        # ensure event is not the same across requests
        self.assertNotEqual(req.environ['cadf_event'].id,
                            self.notifier.notify.call_args_list[0][0][2]['id'])

    def test_project_name_from_oslo_config(self):
        self.assertEqual(self.PROJECT_NAME,
                         self.create_simple_middleware()._conf.project)

    def test_project_name_from_local_config(self):
        project_name = uuid.uuid4().hex
        middleware = self.create_simple_middleware(project=project_name)
        self.assertEqual(project_name, middleware._conf.project)

    def test_no_response(self):
        middleware = self.create_simple_middleware()
        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        req = webob.Request.blank(url,
                                  environ=self.get_environ_header('GET'),
                                  remote_addr='192.168.0.1')
        req.environ['audit.context'] = {}
        middleware._process_request(req)
        payload = req.environ['cadf_event'].as_dict()
        middleware._process_response(req, None)
        payload2 = req.environ['cadf_event'].as_dict()
        self.assertEqual(payload['id'], payload2['id'])
        self.assertEqual(payload['tags'], payload2['tags'])
        self.assertEqual(payload2['outcome'], 'unknown')
        self.assertNotIn('reason', payload2)
        self.assertEqual(len(payload2['reporterchain']), 1)
        self.assertEqual(payload2['reporterchain'][0]['role'], 'modifier')
        self.assertEqual(payload2['reporterchain'][0]['reporter']['id'],
                         'target')

    def test_missing_req(self):
        req = webob.Request.blank('http://admin_host:8774/v2/'
                                  + str(uuid.uuid4()) + '/servers',
                                  environ=self.get_environ_header('GET'))
        req.environ['audit.context'] = {}
        self.assertNotIn('cadf_event', req.environ)

        self.create_simple_middleware()._process_response(req,
                                                          webob.Response())
        self.assertIn('cadf_event', req.environ)
        payload = req.environ['cadf_event'].as_dict()
        self.assertEqual(payload['outcome'], 'success')
        self.assertEqual(payload['reason']['reasonType'], 'HTTP')
        self.assertEqual(payload['reason']['reasonCode'], '200')
        self.assertEqual(payload['observer']['id'], 'target')
