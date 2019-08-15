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

import uuid

from pycadf import cadftaxonomy as taxonomy
import webob

from keystonemiddleware import audit
from keystonemiddleware.tests.unit.audit import base


class AuditApiLogicTest(base.BaseAuditMiddlewareTest):

    def get_payload(self, method, url,
                    audit_map=None, body=None, environ=None):
        audit_map = audit_map or self.audit_map
        environ = environ or self.get_environ_header()

        req = webob.Request.blank(url,
                                  body=body,
                                  method=method,
                                  environ=environ,
                                  remote_addr='192.168.0.1')

        middleware = audit.OpenStackAuditApi(audit_map)
        return middleware._create_event(req).as_dict()

    def test_get_list(self):
        path = '/v2/' + str(uuid.uuid4()) + '/servers'
        url = 'http://admin_host:8774' + path
        payload = self.get_payload('GET', url)

        self.assertEqual(payload['action'], 'read/list')
        self.assertEqual(payload['typeURI'],
                         'http://schemas.dmtf.org/cloud/audit/1.0/event')
        self.assertEqual(payload['outcome'], 'pending')
        self.assertEqual(payload['eventType'], 'activity')
        self.assertEqual(payload['target']['name'], 'nova')
        self.assertEqual(payload['target']['id'], 'resource_id')
        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers')
        self.assertEqual(len(payload['target']['addresses']), 3)
        self.assertEqual(payload['target']['addresses'][0]['name'], 'admin')
        self.assertEqual(payload['target']['addresses'][0]['url'],
                         'http://admin_host:8774')
        self.assertEqual(payload['initiator']['id'], 'user_id')
        self.assertEqual(payload['initiator']['name'], 'user_name')
        self.assertEqual(payload['initiator']['project_id'],
                         'tenant_id')
        self.assertEqual(payload['initiator']['host']['address'],
                         '192.168.0.1')
        self.assertEqual(payload['initiator']['typeURI'],
                         'service/security/account/user')
        self.assertNotEqual(payload['initiator']['credential']['token'],
                            'token')
        self.assertEqual(payload['initiator']['credential']['identity_status'],
                         'Confirmed')
        self.assertNotIn('reason', payload)
        self.assertNotIn('reporterchain', payload)
        self.assertEqual(payload['observer']['id'], 'target')
        self.assertEqual(path, payload['requestPath'])

    def test_get_read(self):
        url = 'http://admin_host:8774/v2/%s/servers/%s' % (uuid.uuid4().hex,
                                                           uuid.uuid4().hex)
        payload = self.get_payload('GET', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers/server')
        self.assertEqual(payload['action'], 'read')
        self.assertEqual(payload['outcome'], 'pending')

    def test_get_unknown_endpoint(self):
        url = 'http://unknown:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('GET', url)

        self.assertEqual(payload['action'], 'read/list')
        self.assertEqual(payload['outcome'], 'pending')
        self.assertEqual(payload['target']['name'], 'unknown')
        self.assertEqual(payload['target']['id'], 'unknown')
        self.assertEqual(payload['target']['typeURI'], 'unknown')

    def test_get_unknown_endpoint_default_set(self):
        with open(self.audit_map, "w") as f:
            f.write("[DEFAULT]\n")
            f.write("target_endpoint_type = compute\n")
            f.write("[path_keywords]\n")
            f.write("servers = server\n\n")
            f.write("[service_endpoints]\n")
            f.write("compute = service/compute")

        url = 'http://unknown:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('GET', url)

        self.assertEqual(payload['action'], 'read/list')
        self.assertEqual(payload['outcome'], 'pending')
        self.assertEqual(payload['target']['name'], 'nova')
        self.assertEqual(payload['target']['id'], 'resource_id')
        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers')

    def test_put(self):
        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('PUT', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers')
        self.assertEqual(payload['action'], 'update')
        self.assertEqual(payload['outcome'], 'pending')

    def test_delete(self):
        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('DELETE', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers')
        self.assertEqual(payload['action'], 'delete')
        self.assertEqual(payload['outcome'], 'pending')

    def test_head(self):
        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('HEAD', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers')
        self.assertEqual(payload['action'], 'read')
        self.assertEqual(payload['outcome'], 'pending')

    def test_post_update(self):
        url = 'http://admin_host:8774/v2/%s/servers/%s' % (uuid.uuid4().hex,
                                                           uuid.uuid4().hex)
        payload = self.get_payload('POST', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers/server')
        self.assertEqual(payload['action'], 'update')
        self.assertEqual(payload['outcome'], 'pending')

    def test_post_create(self):
        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('POST', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers')
        self.assertEqual(payload['action'], 'create')
        self.assertEqual(payload['outcome'], 'pending')

    def test_post_action(self):
        url = 'http://admin_host:8774/v2/%s/servers/action' % uuid.uuid4().hex
        body = b'{"createImage" : {"name" : "new-image","metadata": ' \
               b'{"ImageType": "Gold","ImageVersion": "2.0"}}}'
        payload = self.get_payload('POST', url, body=body)
        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers/action')
        self.assertEqual(payload['action'], 'update/createImage')
        self.assertEqual(payload['outcome'], 'pending')

    def test_post_empty_body_action(self):
        url = 'http://admin_host:8774/v2/%s/servers/action' % uuid.uuid4().hex
        payload = self.get_payload('POST', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/servers/action')
        self.assertEqual(payload['action'], 'create')
        self.assertEqual(payload['outcome'], 'pending')

    def test_custom_action(self):
        url = 'http://admin_host:8774/v2/%s/os-hosts/%s/reboot' % (
            uuid.uuid4().hex, uuid.uuid4().hex)
        payload = self.get_payload('GET', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/os-hosts/host/reboot')
        self.assertEqual(payload['action'], 'start/reboot')
        self.assertEqual(payload['outcome'], 'pending')

    def test_custom_action_complex(self):
        url = 'http://admin_host:8774/v2/%s/os-migrations' % uuid.uuid4().hex
        payload = self.get_payload('GET', url)

        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/os-migrations')
        self.assertEqual(payload['action'], 'read')
        payload = self.get_payload('POST', url)
        self.assertEqual(payload['target']['typeURI'],
                         'service/compute/os-migrations')
        self.assertEqual(payload['action'], 'create')

    def test_response_mod_msg(self):
        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        req = webob.Request.blank(url,
                                  environ=self.get_environ_header('GET'),
                                  remote_addr='192.168.0.1')
        req.environ['audit.context'] = {}
        middleware = self.create_simple_middleware()
        middleware._process_request(req)
        payload = req.environ['cadf_event'].as_dict()
        middleware._process_response(req, webob.Response())
        payload2 = req.environ['cadf_event'].as_dict()
        self.assertEqual(payload['id'], payload2['id'])
        self.assertEqual(payload['tags'], payload2['tags'])
        self.assertEqual(payload2['outcome'], 'success')
        self.assertEqual(payload2['reason']['reasonType'], 'HTTP')
        self.assertEqual(payload2['reason']['reasonCode'], '200')
        self.assertEqual(len(payload2['reporterchain']), 1)
        self.assertEqual(payload2['reporterchain'][0]['role'], 'modifier')
        self.assertEqual(payload2['reporterchain'][0]['reporter']['id'],
                         'target')

    def test_missing_catalog_endpoint_id(self):
        env_headers = {'HTTP_X_SERVICE_CATALOG':
                       '''[{"endpoints_links": [],
                            "endpoints": [{"adminURL":
                                           "http://admin_host:8774",
                                           "region": "RegionOne",
                                           "publicURL":
                                           "http://public_host:8774",
                                           "internalURL":
                                           "http://internal_host:8774"}],
                            "type": "compute",
                            "name": "nova"}]''',
                       'HTTP_X_USER_ID': 'user_id',
                       'HTTP_X_USER_NAME': 'user_name',
                       'HTTP_X_AUTH_TOKEN': 'token',
                       'HTTP_X_PROJECT_ID': 'tenant_id',
                       'HTTP_X_IDENTITY_STATUS': 'Confirmed',
                       'REQUEST_METHOD': 'GET'}

        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('GET', url, environ=env_headers)
        self.assertEqual(payload['target']['id'], 'nova')

    def test_endpoint_missing_internal_url(self):
        env_headers = {'HTTP_X_SERVICE_CATALOG':
                       '''[{"endpoints_links": [],
                            "endpoints": [{"adminURL":
                                           "http://admin_host:8774",
                                           "region": "RegionOne",
                                           "publicURL":
                                           "http://public_host:8774"}],
                             "type": "compute",
                             "name": "nova"}]''',
                       'HTTP_X_USER_ID': 'user_id',
                       'HTTP_X_USER_NAME': 'user_name',
                       'HTTP_X_AUTH_TOKEN': 'token',
                       'HTTP_X_PROJECT_ID': 'tenant_id',
                       'HTTP_X_IDENTITY_STATUS': 'Confirmed',
                       'REQUEST_METHOD': 'GET'}

        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('GET', url, environ=env_headers)
        self.assertEqual((payload['target']['addresses'][1]['url']), "unknown")

    def test_endpoint_missing_public_url(self):
        env_headers = {'HTTP_X_SERVICE_CATALOG':
                       '''[{"endpoints_links": [],
                            "endpoints": [{"adminURL":
                                           "http://admin_host:8774",
                                           "region": "RegionOne",
                                           "internalURL":
                                           "http://internal_host:8774"}],
                             "type": "compute",
                             "name": "nova"}]''',
                       'HTTP_X_USER_ID': 'user_id',
                       'HTTP_X_USER_NAME': 'user_name',
                       'HTTP_X_AUTH_TOKEN': 'token',
                       'HTTP_X_PROJECT_ID': 'tenant_id',
                       'HTTP_X_IDENTITY_STATUS': 'Confirmed',
                       'REQUEST_METHOD': 'GET'}

        url = 'http://admin_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('GET', url, environ=env_headers)
        self.assertEqual((payload['target']['addresses'][2]['url']), "unknown")

    def test_endpoint_missing_admin_url(self):
        env_headers = {'HTTP_X_SERVICE_CATALOG':
                       '''[{"endpoints_links": [],
                            "endpoints": [{"region": "RegionOne",
                                           "publicURL":
                                           "http://public_host:8774",
                                           "internalURL":
                                           "http://internal_host:8774"}],
                             "type": "compute",
                             "name": "nova"}]''',
                       'HTTP_X_USER_ID': 'user_id',
                       'HTTP_X_USER_NAME': 'user_name',
                       'HTTP_X_AUTH_TOKEN': 'token',
                       'HTTP_X_PROJECT_ID': 'tenant_id',
                       'HTTP_X_IDENTITY_STATUS': 'Confirmed',
                       'REQUEST_METHOD': 'GET'}

        url = 'http://public_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('GET', url, environ=env_headers)
        self.assertEqual((payload['target']['addresses'][0]['url']), "unknown")

    def test_service_with_no_endpoints(self):
        env_headers = {'HTTP_X_SERVICE_CATALOG':
                       '''[{"endpoints_links": [],
                             "endpoints": [],
                             "type": "foo",
                             "name": "bar"}]''',
                       'HTTP_X_USER_ID': 'user_id',
                       'HTTP_X_USER_NAME': 'user_name',
                       'HTTP_X_AUTH_TOKEN': 'token',
                       'HTTP_X_PROJECT_ID': 'tenant_id',
                       'HTTP_X_IDENTITY_STATUS': 'Confirmed',
                       'REQUEST_METHOD': 'GET'}

        url = 'http://public_host:8774/v2/' + str(uuid.uuid4()) + '/servers'
        payload = self.get_payload('GET', url, environ=env_headers)
        self.assertEqual(payload['target']['name'], "unknown")

    def test_endpoint_no_service_port(self):
        with open(self.audit_map, "w") as f:
            f.write("[DEFAULT]\n")
            f.write("target_endpoint_type = load-balancer\n")
            f.write("[path_keywords]\n")
            f.write("loadbalancers = loadbalancer\n\n")
            f.write("[service_endpoints]\n")
            f.write("load-balancer = service/load-balancer")

        env_headers = {'HTTP_X_SERVICE_CATALOG':
                       '''[{"endpoints_links": [],
                            "endpoints": [{"adminURL":
                                           "http://admin_host/compute",
                                           "region": "RegionOne",
                                           "publicURL":
                                           "http://public_host/compute"}],
                             "type": "compute",
                             "name": "nova"},
                           {"endpoints_links": [],
                            "endpoints": [{"adminURL":
                                           "http://admin_host/load-balancer",
                                           "region": "RegionOne",
                                           "publicURL":
                                           "http://public_host/load-balancer"}],
                             "type": "load-balancer",
                             "name": "octavia"}]''',
                       'HTTP_X_USER_ID': 'user_id',
                       'HTTP_X_USER_NAME': 'user_name',
                       'HTTP_X_AUTH_TOKEN': 'token',
                       'HTTP_X_PROJECT_ID': 'tenant_id',
                       'HTTP_X_IDENTITY_STATUS': 'Confirmed',
                       'REQUEST_METHOD': 'GET'}

        url = ('http://admin_host/load-balancer/v2/loadbalancers/' +
               str(uuid.uuid4()))
        payload = self.get_payload('GET', url, environ=env_headers)
        self.assertEqual(payload['target']['id'], 'octavia')

    def test_no_auth_token(self):
        # Test cases where API requests such as Swift list public containers
        # which does not require an auth token. In these cases, CADF event
        # should have the defaults (i.e taxonomy.UNKNOWN) instead of raising
        # an exception.
        env_headers = {'HTTP_X_IDENTITY_STATUS': 'Invalid',
                       'REQUEST_METHOD': 'GET'}

        path = '/v1/' + str(uuid.uuid4())
        url = 'https://23.253.72.207' + path
        payload = self.get_payload('GET', url, environ=env_headers)

        self.assertEqual(payload['action'], 'read')
        self.assertEqual(payload['typeURI'],
                         'http://schemas.dmtf.org/cloud/audit/1.0/event')
        self.assertEqual(payload['outcome'], 'pending')
        self.assertEqual(payload['eventType'], 'activity')
        self.assertEqual(payload['target']['name'], taxonomy.UNKNOWN)
        self.assertEqual(payload['target']['id'], taxonomy.UNKNOWN)
        self.assertEqual(payload['target']['typeURI'], taxonomy.UNKNOWN)
        self.assertNotIn('addresses', payload['target'])
        self.assertEqual(payload['initiator']['id'], taxonomy.UNKNOWN)
        self.assertEqual(payload['initiator']['name'], taxonomy.UNKNOWN)
        self.assertEqual(payload['initiator']['project_id'],
                         taxonomy.UNKNOWN)
        self.assertEqual(payload['initiator']['host']['address'],
                         '192.168.0.1')
        self.assertEqual(payload['initiator']['typeURI'],
                         'service/security/account/user')
        self.assertNotEqual(payload['initiator']['credential']['token'],
                            None)
        self.assertEqual(payload['initiator']['credential']['identity_status'],
                         'Invalid')
        self.assertNotIn('reason', payload)
        self.assertNotIn('reporterchain', payload)
        self.assertEqual(payload['observer']['id'], 'target')
        self.assertEqual(path, payload['requestPath'])

    def test_request_and_global_request_id(self):
        path = '/v1/' + str(uuid.uuid4())
        url = 'https://23.253.72.207' + path

        request_id = 'req-%s' % uuid.uuid4()
        global_request_id = 'req-%s' % uuid.uuid4()

        env_headers = self.get_environ_header('GET')
        env_headers['openstack.request_id'] = request_id
        env_headers['openstack.global_request_id'] = global_request_id

        payload = self.get_payload('GET', url, environ=env_headers)

        self.assertEqual(payload['initiator']['request_id'], request_id)
        self.assertEqual(payload['initiator']['global_request_id'],
                         global_request_id)

        payload = self.get_payload('GET', url)

        self.assertNotIn('request_id', payload['initiator'])
        self.assertNotIn('global_request_id', payload['initiator'])
