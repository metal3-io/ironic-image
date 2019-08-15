# Copyright (c) 2014 OpenStack Foundation.
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

import stevedore
from testtools import matchers

from keystonemiddleware.auth_token import _opts as new_opts
from keystonemiddleware import opts as old_opts
from keystonemiddleware.tests.unit import utils


class OptsTestCase(utils.TestCase):

    def test_original_list_all_options(self):
        result_of_old_opts = old_opts.list_auth_token_opts()
        self.assertThat(result_of_old_opts, matchers.HasLength(1))

        for group in (g for (g, _l) in result_of_old_opts):
            self.assertEqual('keystone_authtoken', group)

        # This is the original list that includes deprecated options
        expected_opt_names = [
            'auth_admin_prefix',
            'auth_host',
            'interface',
            'auth_port',
            'auth_protocol',
            'www_authenticate_uri',
            'auth_uri',
            'identity_uri',
            'auth_version',
            'delay_auth_decision',
            'http_connect_timeout',
            'http_request_max_retries',
            'admin_token',
            'admin_user',
            'admin_password',
            'admin_tenant_name',
            'cache',
            'certfile',
            'keyfile',
            'cafile',
            'region_name',
            'insecure',
            'memcached_servers',
            'token_cache_time',
            'memcache_security_strategy',
            'memcache_secret_key',
            'memcache_use_advanced_pool',
            'memcache_pool_dead_retry',
            'memcache_pool_maxsize',
            'memcache_pool_unused_timeout',
            'memcache_pool_conn_get_timeout',
            'memcache_pool_socket_timeout',
            'include_service_catalog',
            'enforce_token_bind',
            'auth_type',
            'auth_section',
            'service_token_roles',
            'service_token_roles_required',
            'service_type',
        ]
        opt_names = [o.name for (g, l) in result_of_old_opts for o in l]
        self.assertThat(opt_names, matchers.HasLength(len(expected_opt_names)))

        for opt in opt_names:
            self.assertIn(opt, expected_opt_names)

    def _test_list_auth_token_opts(self, result):
        self.assertThat(result, matchers.HasLength(1))

        for group in (g for (g, _l) in result):
            self.assertEqual('keystone_authtoken', group)

        # This is the sample config generator list WITHOUT deprecations
        expected_opt_names = [
            'www_authenticate_uri',
            'interface',
            'auth_uri',
            'auth_version',
            'delay_auth_decision',
            'http_connect_timeout',
            'http_request_max_retries',
            'cache',
            'certfile',
            'keyfile',
            'cafile',
            'region_name',
            'insecure',
            'memcached_servers',
            'token_cache_time',
            'memcache_security_strategy',
            'memcache_secret_key',
            'memcache_use_advanced_pool',
            'memcache_pool_dead_retry',
            'memcache_pool_maxsize',
            'memcache_pool_unused_timeout',
            'memcache_pool_conn_get_timeout',
            'memcache_pool_socket_timeout',
            'include_service_catalog',
            'enforce_token_bind',
            'auth_type',
            'auth_section',
            'service_token_roles',
            'service_token_roles_required',
            'service_type',
        ]
        opt_names = [o.name for (g, l) in result for o in l]
        self.assertThat(opt_names, matchers.HasLength(len(expected_opt_names)))

        for opt in opt_names:
            self.assertIn(opt, expected_opt_names)

    def test_list_auth_token_opts(self):
        self._test_list_auth_token_opts(new_opts.list_opts())

    def test_entry_point(self):
        em = stevedore.ExtensionManager('oslo.config.opts',
                                        invoke_on_load=True)
        for extension in em:
            if extension.name == 'keystonemiddleware.auth_token':
                break
        else:
            self.fail('keystonemiddleware.auth_token not found')

        self._test_list_auth_token_opts(extension.obj)
