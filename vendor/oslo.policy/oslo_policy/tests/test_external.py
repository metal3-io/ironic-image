# Copyright (c) 2015 OpenStack Foundation.
# All Rights Reserved.

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

import json
import mock
from oslo_serialization import jsonutils
from requests_mock.contrib import fixture as rm_fixture
import six.moves.urllib.parse as urlparse

from oslo_policy import _external
from oslo_policy import opts
from oslo_policy.tests import base


class HttpCheckTestCase(base.PolicyBaseTestCase):

    def setUp(self):
        super(HttpCheckTestCase, self).setUp()
        opts._register(self.conf)
        self.requests_mock = self.useFixture(rm_fixture.Fixture())

    def decode_post_data(self, post_data):
        result = {}
        for item in post_data.split('&'):
            key, _sep, value = item.partition('=')
            result[key] = jsonutils.loads(urlparse.unquote_plus(value))
        return result

    def test_accept(self):
        self.requests_mock.post('http://example.com/target', text='True')

        check = _external.HttpCheck('http', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        self.assertTrue(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('application/x-www-form-urlencoded',
                         last_request.headers['Content-Type'])
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(target=target_dict, credentials=cred_dict,
                              rule=None),
                         self.decode_post_data(last_request.body))

    def test_accept_json(self):
        self.conf.set_override('remote_content_type', 'application/json',
                               group='oslo_policy')
        self.requests_mock.post('http://example.com/target', text='True')

        check = _external.HttpCheck('http', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        self.assertTrue(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('application/json',
                         last_request.headers['Content-Type'])
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(rule=None,
                              credentials=cred_dict,
                              target=target_dict),
                         json.loads(last_request.body.decode('utf-8')))

    def test_reject(self):
        self.requests_mock.post("http://example.com/target", text='other')

        check = _external.HttpCheck('http', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        self.assertFalse(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(target=target_dict, credentials=cred_dict,
                              rule=None),
                         self.decode_post_data(last_request.body))

    def test_http_with_objects_in_target(self):
        self.requests_mock.post("http://example.com/target", text='True')

        check = _external.HttpCheck('http', '//example.com/%(name)s')
        target = {'a': object(),
                  'name': 'target',
                  'b': 'test data'}
        self.assertTrue(check(target,
                              dict(user='user', roles=['a', 'b', 'c']),
                              self.enforcer))

    def test_http_with_strings_in_target(self):
        self.requests_mock.post("http://example.com/target", text='True')

        check = _external.HttpCheck('http', '//example.com/%(name)s')
        target = {'a': 'some_string',
                  'name': 'target',
                  'b': 'test data'}
        self.assertTrue(check(target,
                              dict(user='user', roles=['a', 'b', 'c']),
                              self.enforcer))

    def test_accept_with_rule_in_argument(self):
        self.requests_mock.post('http://example.com/target', text='True')

        check = _external.HttpCheck('http', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        current_rule = "a_rule"
        self.assertTrue(check(target_dict, cred_dict, self.enforcer,
                              current_rule))

        last_request = self.requests_mock.last_request
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(target=target_dict, credentials=cred_dict,
                              rule=current_rule),
                         self.decode_post_data(last_request.body))

    def test_reject_with_rule_in_argument(self):
        self.requests_mock.post("http://example.com/target", text='other')

        check = _external.HttpCheck('http', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        current_rule = "a_rule"
        self.assertFalse(check(target_dict, cred_dict, self.enforcer,
                               current_rule))

        last_request = self.requests_mock.last_request
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(target=target_dict, credentials=cred_dict,
                              rule=current_rule),
                         self.decode_post_data(last_request.body))


class HttpsCheckTestCase(base.PolicyBaseTestCase):

    def setUp(self):
        super(HttpsCheckTestCase, self).setUp()
        opts._register(self.conf)
        self.requests_mock = self.useFixture(rm_fixture.Fixture())

    def decode_post_data(self, post_data):
        result = {}
        for item in post_data.split('&'):
            key, _sep, value = item.partition('=')
            result[key] = jsonutils.loads(urlparse.unquote_plus(value))
        return result

    def test_https_accept(self):
        self.requests_mock.post('https://example.com/target', text='True')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        self.assertTrue(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('application/x-www-form-urlencoded',
                         last_request.headers['Content-Type'])
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(rule=None,
                              target=target_dict,
                              credentials=cred_dict),
                         self.decode_post_data(last_request.body))

    def test_https_accept_json(self):
        self.conf.set_override('remote_content_type', 'application/json',
                               group='oslo_policy')
        self.requests_mock.post('https://example.com/target', text='True')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        self.assertTrue(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('application/json',
                         last_request.headers['Content-Type'])
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(rule=None,
                              target=target_dict,
                              credentials=cred_dict),
                         json.loads(last_request.body.decode('utf-8')))

    def test_https_accept_with_verify(self):
        self.conf.set_override('remote_ssl_verify_server_crt', True,
                               group='oslo_policy')
        self.requests_mock.post('https://example.com/target', text='True')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        self.assertTrue(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual(True, last_request.verify)
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(rule=None,
                              target=target_dict,
                              credentials=cred_dict),
                         self.decode_post_data(last_request.body))

    def test_https_accept_with_verify_cert(self):
        self.conf.set_override('remote_ssl_verify_server_crt', True,
                               group='oslo_policy')
        self.conf.set_override('remote_ssl_ca_crt_file', "ca.crt",
                               group='oslo_policy')
        self.requests_mock.post('https://example.com/target', text='True')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        with mock.patch('os.path.exists') as path_exists:
            path_exists.return_value = True
            self.assertTrue(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('ca.crt', last_request.verify)
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(rule=None,
                              target=target_dict,
                              credentials=cred_dict),
                         self.decode_post_data(last_request.body))

    def test_https_accept_with_verify_and_client_certs(self):
        self.conf.set_override('remote_ssl_verify_server_crt', True,
                               group='oslo_policy')
        self.conf.set_override('remote_ssl_ca_crt_file', "ca.crt",
                               group='oslo_policy')
        self.conf.set_override('remote_ssl_client_key_file', "client.key",
                               group='oslo_policy')
        self.conf.set_override('remote_ssl_client_crt_file', "client.crt",
                               group='oslo_policy')
        self.requests_mock.post('https://example.com/target', text='True')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        with mock.patch('os.path.exists') as path_exists:
            with mock.patch('os.access') as os_access:
                path_exists.return_value = True
                os_access.return_value = True
                self.assertTrue(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('ca.crt', last_request.verify)
        self.assertEqual(('client.crt', 'client.key'), last_request.cert)
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(rule=None,
                              target=target_dict,
                              credentials=cred_dict),
                         self.decode_post_data(last_request.body))

    def test_https_reject(self):
        self.requests_mock.post("https://example.com/target", text='other')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')

        target_dict = dict(name='target', spam='spammer')
        cred_dict = dict(user='user', roles=['a', 'b', 'c'])
        self.assertFalse(check(target_dict, cred_dict, self.enforcer))

        last_request = self.requests_mock.last_request
        self.assertEqual('POST', last_request.method)
        self.assertEqual(dict(rule=None,
                              target=target_dict,
                              credentials=cred_dict),
                         self.decode_post_data(last_request.body))

    def test_https_with_objects_in_target(self):
        self.requests_mock.post("https://example.com/target", text='True')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')
        target = {'a': object(),
                  'name': 'target',
                  'b': 'test data'}
        self.assertTrue(check(target,
                              dict(user='user', roles=['a', 'b', 'c']),
                              self.enforcer))

    def test_https_with_strings_in_target(self):
        self.requests_mock.post("https://example.com/target", text='True')

        check = _external.HttpsCheck('https', '//example.com/%(name)s')
        target = {'a': 'some_string',
                  'name': 'target',
                  'b': 'test data'}
        self.assertTrue(check(target,
                              dict(user='user', roles=['a', 'b', 'c']),
                              self.enforcer))
