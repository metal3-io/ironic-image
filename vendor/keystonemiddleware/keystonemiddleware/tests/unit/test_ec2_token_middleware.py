# Copyright 2012 OpenStack Foundation
#
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

import mock
from oslo_serialization import jsonutils
import requests
import six
import webob

from keystonemiddleware import ec2_token
from keystonemiddleware.tests.unit import utils


TOKEN_ID = 'fake-token-id'
GOOD_RESPONSE = {'access': {'token': {'id': TOKEN_ID,
                                      'tenant': {'id': 'TENANT_ID'}}}}
EMPTY_RESPONSE = {}


class FakeResponse(object):
    reason = "Test Reason"

    def __init__(self, json, status_code=400):
        self._json = json
        self.status_code = status_code

    def json(self):
        return self._json


class FakeApp(object):
    """This represents a WSGI app protected by the auth_token middleware."""

    def __call__(self, env, start_response):
        resp = webob.Response()
        resp.environ = env
        return resp(env, start_response)


class EC2TokenMiddlewareTestBase(utils.TestCase):

    TEST_PROTOCOL = 'https'
    TEST_HOST = 'fakehost'
    TEST_PORT = 35357
    TEST_URL = '%s://%s:%d/v2.0/ec2tokens' % (TEST_PROTOCOL,
                                              TEST_HOST,
                                              TEST_PORT)

    def setUp(self):
        super(EC2TokenMiddlewareTestBase, self).setUp()
        self.middleware = ec2_token.EC2Token(FakeApp(), {})

    def _validate_ec2_error(self, response, http_status, ec2_code):
        self.assertEqual(http_status, response.status_code,
                         'Expected HTTP status %s' % http_status)
        error_msg = '<Code>%s</Code>' % ec2_code
        if six.PY3:
            # encode error message like main code
            error_msg = error_msg.encode()
        self.assertIn(error_msg, response.body)


class EC2TokenMiddlewareTestGood(EC2TokenMiddlewareTestBase):
    @mock.patch.object(
        requests, 'request',
        return_value=FakeResponse(GOOD_RESPONSE, status_code=200))
    def test_protocol_old_versions(self, mock_request):
        req = webob.Request.blank('/test')
        req.GET['Signature'] = 'test-signature'
        req.GET['AWSAccessKeyId'] = 'test-key-id'
        req.body = b'Action=ListUsers&Version=2010-05-08'
        resp = req.get_response(self.middleware)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(TOKEN_ID, req.headers['X-Auth-Token'])

        mock_request.assert_called_with(
            'POST', 'http://localhost:5000/v2.0/ec2tokens',
            data=mock.ANY, headers={'Content-Type': 'application/json'},
            verify=True, cert=None)

        data = jsonutils.loads(mock_request.call_args[1]['data'])
        expected_data = {
            'ec2Credentials': {
                'access': 'test-key-id',
                'headers': {'Host': 'localhost:80', 'Content-Length': '35'},
                'host': 'localhost:80',
                'verb': 'GET',
                'params': {'AWSAccessKeyId': 'test-key-id'},
                'signature': 'test-signature',
                'path': '/test',
                'body_hash': 'b6359072c78d70ebee1e81adcbab4f01'
                             'bf2c23245fa365ef83fe8f1f955085e2'}}
        self.assertDictEqual(expected_data, data)

    @mock.patch.object(
        requests, 'request',
        return_value=FakeResponse(GOOD_RESPONSE, status_code=200))
    def test_protocol_v4(self, mock_request):
        req = webob.Request.blank('/test')
        auth_str = (
            'AWS4-HMAC-SHA256'
            ' Credential=test-key-id/20110909/us-east-1/iam/aws4_request,'
            ' SignedHeaders=content-type;host;x-amz-date,'
            ' Signature=test-signature')
        req.headers['Authorization'] = auth_str
        req.body = b'Action=ListUsers&Version=2010-05-08'
        resp = req.get_response(self.middleware)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(TOKEN_ID, req.headers['X-Auth-Token'])

        mock_request.assert_called_with(
            'POST', 'http://localhost:5000/v2.0/ec2tokens',
            data=mock.ANY, headers={'Content-Type': 'application/json'},
            verify=True, cert=None)

        data = jsonutils.loads(mock_request.call_args[1]['data'])
        expected_data = {
            'ec2Credentials': {
                'access': 'test-key-id',
                'headers': {'Host': 'localhost:80',
                            'Content-Length': '35',
                            'Authorization': auth_str},
                'host': 'localhost:80',
                'verb': 'GET',
                'params': {},
                'signature': 'test-signature',
                'path': '/test',
                'body_hash': 'b6359072c78d70ebee1e81adcbab4f01'
                             'bf2c23245fa365ef83fe8f1f955085e2'}}
        self.assertDictEqual(expected_data, data)


class EC2TokenMiddlewareTestBad(EC2TokenMiddlewareTestBase):

    def test_no_signature(self):
        req = webob.Request.blank('/test')
        resp = req.get_response(self.middleware)
        self._validate_ec2_error(resp, 400, 'AuthFailure')

    def test_no_key_id(self):
        req = webob.Request.blank('/test')
        req.GET['Signature'] = 'test-signature'
        resp = req.get_response(self.middleware)
        self._validate_ec2_error(resp, 400, 'AuthFailure')

    @mock.patch.object(requests,
                       'request',
                       return_value=FakeResponse(EMPTY_RESPONSE))
    def test_communication_failure(self, mock_request):
        req = webob.Request.blank('/test')
        req.GET['Signature'] = 'test-signature'
        req.GET['AWSAccessKeyId'] = 'test-key-id'
        resp = req.get_response(self.middleware)
        self._validate_ec2_error(resp, 400, 'AuthFailure')
        mock_request.assert_called_with('POST', mock.ANY,
                                        data=mock.ANY, headers=mock.ANY,
                                        verify=mock.ANY, cert=mock.ANY)

    @mock.patch.object(requests,
                       'request',
                       return_value=FakeResponse(EMPTY_RESPONSE))
    def test_no_result_data(self, mock_request):
        req = webob.Request.blank('/test')
        req.GET['Signature'] = 'test-signature'
        req.GET['AWSAccessKeyId'] = 'test-key-id'
        resp = req.get_response(self.middleware)
        self._validate_ec2_error(resp, 400, 'AuthFailure')
        mock_request.assert_called_with('POST', mock.ANY,
                                        data=mock.ANY, headers=mock.ANY,
                                        verify=mock.ANY, cert=mock.ANY)
