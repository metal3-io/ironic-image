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

import fixtures
import six

from keystonemiddleware.auth_token import _cache
from keystonemiddleware.auth_token import _exceptions as exc
from keystonemiddleware.tests.unit.auth_token import base
from keystonemiddleware.tests.unit import utils

MEMCACHED_SERVERS = ['localhost:11211']
MEMCACHED_AVAILABLE = None


class TestCacheSetup(base.BaseAuthTokenTestCase):

    def test_assert_valid_memcache_protection_config(self):
        # test missing memcache_secret_key
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_security_strategy': 'Encrypt'
        }
        self.assertRaises(exc.ConfigurationError,
                          self.create_simple_middleware,
                          conf=conf)
        # test invalue memcache_security_strategy
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_security_strategy': 'whatever'
        }
        self.assertRaises(exc.ConfigurationError,
                          self.create_simple_middleware,
                          conf=conf)
        # test missing memcache_secret_key
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_security_strategy': 'mac'
        }
        self.assertRaises(exc.ConfigurationError,
                          self.create_simple_middleware,
                          conf=conf)
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_security_strategy': 'Encrypt',
            'memcache_secret_key': ''
        }
        self.assertRaises(exc.ConfigurationError,
                          self.create_simple_middleware,
                          conf=conf)
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_security_strategy': 'mAc',
            'memcache_secret_key': ''
        }
        self.assertRaises(exc.ConfigurationError,
                          self.create_simple_middleware,
                          conf=conf)


class NoMemcacheAuthToken(base.BaseAuthTokenTestCase):
    """These tests will not have the memcache module available."""

    def setUp(self):
        super(NoMemcacheAuthToken, self).setUp()
        self.useFixture(utils.DisableModuleFixture('memcache'))

    def test_nomemcache(self):
        conf = {
            'admin_token': 'admin_token1',
            'auth_host': 'keystone.example.com',
            'auth_port': '1234',
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'www_authenticate_uri': 'https://keystone.example.com:1234',
        }

        self.create_simple_middleware(conf=conf)


class TestLiveMemcache(base.BaseAuthTokenTestCase):

    def setUp(self):
        super(TestLiveMemcache, self).setUp()

        global MEMCACHED_AVAILABLE

        if MEMCACHED_AVAILABLE is None:
            try:
                import memcache
                c = memcache.Client(MEMCACHED_SERVERS)
                c.set('ping', 'pong', time=1)
                MEMCACHED_AVAILABLE = c.get('ping') == 'pong'
            except ImportError:
                MEMCACHED_AVAILABLE = False

        if not MEMCACHED_AVAILABLE:
            self.skipTest('memcached not available')

    def test_encrypt_cache_data(self):
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_security_strategy': 'encrypt',
            'memcache_secret_key': 'mysecret'
        }

        token = six.b(uuid.uuid4().hex)
        data = uuid.uuid4().hex

        token_cache = self.create_simple_middleware(conf=conf)._token_cache
        token_cache.initialize({})

        token_cache.set(token, data)
        self.assertEqual(token_cache.get(token), data)

    def test_sign_cache_data(self):
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_security_strategy': 'mac',
            'memcache_secret_key': 'mysecret'
        }

        token = six.b(uuid.uuid4().hex)
        data = uuid.uuid4().hex

        token_cache = self.create_simple_middleware(conf=conf)._token_cache
        token_cache.initialize({})

        token_cache.set(token, data)
        self.assertEqual(token_cache.get(token), data)

    def test_no_memcache_protection(self):
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_secret_key': 'mysecret'
        }

        token = six.b(uuid.uuid4().hex)
        data = uuid.uuid4().hex

        token_cache = self.create_simple_middleware(conf=conf)._token_cache
        token_cache.initialize({})
        token_cache.set(token, data)
        self.assertEqual(token_cache.get(token), data)

    def test_memcache_pool(self):
        conf = {
            'memcached_servers': ','.join(MEMCACHED_SERVERS),
            'memcache_use_advanced_pool': True
        }

        token = six.b(uuid.uuid4().hex)
        data = uuid.uuid4().hex

        token_cache = self.create_simple_middleware(conf=conf)._token_cache
        token_cache.initialize({})

        token_cache.set(token, data)
        self.assertEqual(token_cache.get(token), data)


class TestMemcachePoolAbstraction(utils.TestCase):
    def setUp(self):
        super(TestMemcachePoolAbstraction, self).setUp()
        self.useFixture(fixtures.MockPatch(
            'oslo_cache._memcache_pool._MemcacheClient'))

    def test_abstraction_layer_reserve_places_connection_back_in_pool(self):
        cache_pool = _cache._MemcacheClientPool(
            memcache_servers=[], arguments={}, maxsize=1, unused_timeout=10)
        conn = None
        with cache_pool.reserve() as client:
            self.assertEqual(cache_pool._pool._acquired, 1)
            conn = client

        self.assertEqual(cache_pool._pool._acquired, 0)
        with cache_pool.reserve() as client:
            # Make sure the connection we got before is in-fact the one we
            # get again.
            self.assertEqual(conn, client)
