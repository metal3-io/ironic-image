# Copyright 2010-2013 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Utilities for memcache encryption and integrity check.

Data should be serialized before entering these functions. Encryption
has a dependency on the cryptography module. If cryptography is not
available, CryptoUnavailableError will be raised.

This module will not be called unless signing or encryption is enabled
in the config. It will always validate signatures, and will decrypt
data if encryption is enabled. It is not valid to mix protection
modes.

"""

import base64
import functools
import hashlib
import hmac
import math
import os
import six

from keystonemiddleware.i18n import _
from oslo_utils import secretutils

try:
    from cryptography.hazmat import backends as crypto_backends
    from cryptography.hazmat.primitives import ciphers
    from cryptography.hazmat.primitives.ciphers import algorithms
    from cryptography.hazmat.primitives.ciphers import modes
    from cryptography.hazmat.primitives import padding
except ImportError:
    ciphers = None


HASH_FUNCTION = hashlib.sha384
DIGEST_LENGTH = HASH_FUNCTION().digest_size
DIGEST_SPLIT = DIGEST_LENGTH // 3
DIGEST_LENGTH_B64 = 4 * int(math.ceil(DIGEST_LENGTH / 3.0))


class InvalidMacError(Exception):
    """raise when unable to verify MACed data.

    This usually indicates that data had been expectedly modified in memcache.

    """

    pass


class DecryptError(Exception):
    """raise when unable to decrypt encrypted data."""

    pass


class CryptoUnavailableError(Exception):
    """raise when Python Crypto module is not available."""

    pass


def assert_crypto_availability(f):
    """Ensure cryptography module is available."""
    @functools.wraps(f)
    def wrapper(*args, **kwds):
        if ciphers is None:
            raise CryptoUnavailableError()
        return f(*args, **kwds)
    return wrapper


def derive_keys(token, secret, strategy):
    """Derive keys for MAC and ENCRYPTION from the user-provided secret.

    The resulting keys should be passed to the protect and unprotect functions.

    As suggested by NIST Special Publication 800-108, this uses the
    first 128 bits from the sha384 KDF for the obscured cache key
    value, the second 128 bits for the message authentication key and
    the remaining 128 bits for the encryption key.

    This approach is faster than computing a separate hmac as the KDF
    for each desired key.
    """
    if not isinstance(secret, six.binary_type):
        secret = secret.encode()

    if not isinstance(token, six.binary_type):
        token = token.encode()

    if not isinstance(strategy, six.binary_type):
        strategy = strategy.encode()

    digest = hmac.new(secret, token + strategy, HASH_FUNCTION).digest()
    return {'CACHE_KEY': digest[:DIGEST_SPLIT],
            'MAC': digest[DIGEST_SPLIT: 2 * DIGEST_SPLIT],
            'ENCRYPTION': digest[2 * DIGEST_SPLIT:],
            'strategy': strategy}


def sign_data(key, data):
    """Sign the data using the defined function and the derived key."""
    if not isinstance(key, six.binary_type):
        key = key.encode()

    if not isinstance(data, six.binary_type):
        data = data.encode()

    mac = hmac.new(key, data, HASH_FUNCTION).digest()
    return base64.b64encode(mac)


@assert_crypto_availability
def encrypt_data(key, data):
    """Encrypt the data with the given secret key.

    Padding is n bytes of the value n, where 1 <= n <= blocksize.
    """
    iv = os.urandom(16)
    cipher = ciphers.Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=crypto_backends.default_backend())

    # AES algorithm uses block size of 16 bytes = 128 bits, defined in
    # algorithms.AES.block_size. Previously, we manually padded this using
    # six.int2byte(padding) * padding.  Using ``cryptography``, we will
    # analogously use hazmat.primitives.padding to pad it to
    # the 128-bit block size.
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(data) + padder.finalize()
    encryptor = cipher.encryptor()
    return iv + encryptor.update(padded_data) + encryptor.finalize()


def decrypt_data(key, data):
    """Decrypt the data with the given secret key."""
    iv = data[:16]
    cipher = ciphers.Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=crypto_backends.default_backend())
    try:
        decryptor = cipher.decryptor()
        result = decryptor.update(data[16:]) + decryptor.finalize()
    except Exception:
        raise DecryptError(_('Encrypted data appears to be corrupted.'))

    # Strip the last n padding bytes where n is the last value in
    # the plaintext
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return unpadder.update(result) + unpadder.finalize()


def protect_data(keys, data):
    """Serialize data given a dict of keys.

    Given keys and serialized data, returns an appropriately protected string
    suitable for storage in the cache.

    """
    if keys['strategy'] == b'ENCRYPT':
        data = encrypt_data(keys['ENCRYPTION'], data)

    encoded_data = base64.b64encode(data)

    signature = sign_data(keys['MAC'], encoded_data)
    return signature + encoded_data


def unprotect_data(keys, signed_data):
    """De-serialize data given a dict of keys.

    Given keys and cached string data, verifies the signature, decrypts if
    necessary, and returns the original serialized data.

    """
    # cache backends return None when no data is found. We don't mind
    # that this particular special value is unsigned.
    if signed_data is None:
        return None

    # First we calculate the signature
    provided_mac = signed_data[:DIGEST_LENGTH_B64]
    calculated_mac = sign_data(
        keys['MAC'],
        signed_data[DIGEST_LENGTH_B64:])

    # Then verify that it matches the provided value
    if not secretutils.constant_time_compare(provided_mac, calculated_mac):
        raise InvalidMacError(_('Invalid MAC; data appears to be corrupted.'))

    data = base64.b64decode(signed_data[DIGEST_LENGTH_B64:])

    # then if necessary decrypt the data
    if keys['strategy'] == b'ENCRYPT':
        data = decrypt_data(keys['ENCRYPTION'], data)

    return data


def get_cache_key(keys):
    """Return a cache key.

    Given keys generated by derive_keys(), returns a base64 encoded value
    suitable for use as a cache key in memcached.

    """
    return base64.b64encode(keys['CACHE_KEY'])
