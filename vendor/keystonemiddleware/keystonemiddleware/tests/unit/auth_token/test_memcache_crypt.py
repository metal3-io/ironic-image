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

import six

from keystonemiddleware.auth_token import _memcache_crypt as memcache_crypt
from keystonemiddleware.tests.unit import utils


class MemcacheCryptPositiveTests(utils.BaseTestCase):
    def _setup_keys(self, strategy):
        return memcache_crypt.derive_keys('token', 'secret', strategy)

    def test_derive_keys(self):
        keys = self._setup_keys(b'strategy')
        self.assertEqual(len(keys['ENCRYPTION']),
                         len(keys['CACHE_KEY']))
        self.assertEqual(len(keys['CACHE_KEY']),
                         len(keys['MAC']))
        self.assertNotEqual(keys['ENCRYPTION'],
                            keys['MAC'])
        self.assertIn('strategy', keys.keys())

    def test_key_strategy_diff(self):
        k1 = self._setup_keys(b'MAC')
        k2 = self._setup_keys(b'ENCRYPT')
        self.assertNotEqual(k1, k2)

    def test_sign_data(self):
        keys = self._setup_keys(b'MAC')
        sig = memcache_crypt.sign_data(keys['MAC'], b'data')
        self.assertEqual(len(sig), memcache_crypt.DIGEST_LENGTH_B64)

    def test_encryption(self):
        keys = self._setup_keys(b'ENCRYPT')
        # what you put in is what you get out
        for data in [b'data', b'1234567890123456', b'\x00\xFF' * 13
                     ] + [six.int2byte(x % 256) * x for x in range(768)]:
            crypt = memcache_crypt.encrypt_data(keys['ENCRYPTION'], data)
            decrypt = memcache_crypt.decrypt_data(keys['ENCRYPTION'], crypt)
            self.assertEqual(data, decrypt)
            self.assertRaises(memcache_crypt.DecryptError,
                              memcache_crypt.decrypt_data,
                              keys['ENCRYPTION'], crypt[:-1])

    def test_protect_wrappers(self):
        data = b'My Pretty Little Data'
        for strategy in [b'MAC', b'ENCRYPT']:
            keys = self._setup_keys(strategy)
            protected = memcache_crypt.protect_data(keys, data)
            self.assertNotEqual(protected, data)
            if strategy == b'ENCRYPT':
                self.assertNotIn(data, protected)
            unprotected = memcache_crypt.unprotect_data(keys, protected)
            self.assertEqual(data, unprotected)
            self.assertRaises(memcache_crypt.InvalidMacError,
                              memcache_crypt.unprotect_data,
                              keys, protected[:-1])
            self.assertIsNone(memcache_crypt.unprotect_data(keys, None))

    def test_no_cryptography(self):
        aes = memcache_crypt.ciphers
        memcache_crypt.ciphers = None
        self.assertRaises(memcache_crypt.CryptoUnavailableError,
                          memcache_crypt.encrypt_data, 'token', 'secret',
                          'data')
        memcache_crypt.ciphers = aes
