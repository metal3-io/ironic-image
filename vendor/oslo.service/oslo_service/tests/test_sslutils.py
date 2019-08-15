# Copyright 2015 Mirantis, Inc.
#
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

import mock
import os
import ssl

from oslo_config import cfg

from oslo_service import sslutils
from oslo_service.tests import base


CONF = cfg.CONF

SSL_CERT_DIR = os.path.normpath(os.path.join(
                                os.path.dirname(os.path.abspath(__file__)),
                                'ssl_cert'))


class SslutilsTestCase(base.ServiceBaseTestCase):
    """Test cases for sslutils."""

    def setUp(self):
        super(SslutilsTestCase, self).setUp()
        self.cert_file_name = os.path.join(SSL_CERT_DIR, 'certificate.crt')
        self.key_file_name = os.path.join(SSL_CERT_DIR, 'privatekey.key')
        self.ca_file_name = os.path.join(SSL_CERT_DIR, 'ca.crt')

    @mock.patch("%s.RuntimeError" % RuntimeError.__module__)
    @mock.patch("os.path.exists")
    def test_is_enabled(self, exists_mock, runtime_error_mock):
        exists_mock.return_value = True
        self.conf.set_default("cert_file", self.cert_file_name,
                              group=sslutils.config_section)
        self.conf.set_default("key_file", self.key_file_name,
                              group=sslutils.config_section)
        self.conf.set_default("ca_file", self.ca_file_name,
                              group=sslutils.config_section)
        sslutils.is_enabled(self.conf)
        self.assertFalse(runtime_error_mock.called)

    @mock.patch("os.path.exists")
    def test_is_enabled_no_ssl_cert_file_fails(self, exists_mock):
        exists_mock.side_effect = [False]
        self.conf.set_default("cert_file", "/no/such/file",
                              group=sslutils.config_section)
        self.assertRaises(RuntimeError, sslutils.is_enabled, self.conf)

    @mock.patch("os.path.exists")
    def test_is_enabled_no_ssl_key_file_fails(self, exists_mock):
        exists_mock.side_effect = [True, False]
        self.conf.set_default("cert_file", self.cert_file_name,
                              group=sslutils.config_section)
        self.conf.set_default("key_file", "/no/such/file",
                              group=sslutils.config_section)
        self.assertRaises(RuntimeError, sslutils.is_enabled, self.conf)

    @mock.patch("os.path.exists")
    def test_is_enabled_no_ssl_ca_file_fails(self, exists_mock):
        exists_mock.side_effect = [True, True, False]
        self.conf.set_default("cert_file", self.cert_file_name,
                              group=sslutils.config_section)
        self.conf.set_default("key_file", self.key_file_name,
                              group=sslutils.config_section)
        self.conf.set_default("ca_file", "/no/such/file",
                              group=sslutils.config_section)
        self.assertRaises(RuntimeError, sslutils.is_enabled, self.conf)

    @mock.patch("ssl.wrap_socket")
    @mock.patch("os.path.exists")
    def _test_wrap(self, exists_mock, wrap_socket_mock, **kwargs):
        exists_mock.return_value = True
        sock = mock.Mock()
        self.conf.set_default("cert_file", self.cert_file_name,
                              group=sslutils.config_section)
        self.conf.set_default("key_file", self.key_file_name,
                              group=sslutils.config_section)
        ssl_kwargs = {'server_side': True,
                      'certfile': self.conf.ssl.cert_file,
                      'keyfile': self.conf.ssl.key_file,
                      'cert_reqs': ssl.CERT_NONE,
                      }
        if kwargs:
            ssl_kwargs.update(**kwargs)
        sslutils.wrap(self.conf, sock)
        wrap_socket_mock.assert_called_once_with(sock, **ssl_kwargs)

    def test_wrap(self):
        self._test_wrap()

    def test_wrap_ca_file(self):
        self.conf.set_default("ca_file", self.ca_file_name,
                              group=sslutils.config_section)
        ssl_kwargs = {'ca_certs': self.conf.ssl.ca_file,
                      'cert_reqs': ssl.CERT_REQUIRED
                      }
        self._test_wrap(**ssl_kwargs)

    def test_wrap_ciphers(self):
        self.conf.set_default("ca_file", self.ca_file_name,
                              group=sslutils.config_section)
        ciphers = (
            'ECDH+AESGCM:DH+AESGCM:ECDH+AES256:DH+AES256:ECDH+AES128:DH+'
            'AES:ECDH+HIGH:DH+HIGH:ECDH+3DES:DH+3DES:RSA+AESGCM:RSA+AES:'
            'RSA+HIGH:RSA+3DES:!aNULL:!eNULL:!MD5:!DSS:!RC4'
        )
        self.conf.set_default("ciphers", ciphers,
                              group=sslutils.config_section)
        ssl_kwargs = {'ca_certs': self.conf.ssl.ca_file,
                      'cert_reqs': ssl.CERT_REQUIRED,
                      'ciphers': ciphers}
        self._test_wrap(**ssl_kwargs)

    def test_wrap_ssl_version(self):
        self.conf.set_default("ca_file", self.ca_file_name,
                              group=sslutils.config_section)
        self.conf.set_default("version", "tlsv1",
                              group=sslutils.config_section)
        ssl_kwargs = {'ca_certs': self.conf.ssl.ca_file,
                      'cert_reqs': ssl.CERT_REQUIRED,
                      'ssl_version': ssl.PROTOCOL_TLSv1}
        self._test_wrap(**ssl_kwargs)
