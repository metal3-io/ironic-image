# Copyright 2011 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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

"""Unit tests for `wsgi`."""

import os
import platform
import six
import socket
import tempfile
import testtools

import eventlet
import eventlet.wsgi
import mock
import requests
import webob

from oslo_config import cfg
from oslo_service import sslutils
from oslo_service.tests import base
from oslo_service import wsgi
from oslo_utils import netutils


SSL_CERT_DIR = os.path.normpath(os.path.join(
                                os.path.dirname(os.path.abspath(__file__)),
                                'ssl_cert'))
CONF = cfg.CONF


class WsgiTestCase(base.ServiceBaseTestCase):
    """Base class for WSGI tests."""

    def setUp(self):
        super(WsgiTestCase, self).setUp()
        self.conf(args=[], default_config_files=[])


class TestLoaderNothingExists(WsgiTestCase):
    """Loader tests where os.path.exists always returns False."""

    def setUp(self):
        super(TestLoaderNothingExists, self).setUp()
        mock_patcher = mock.patch.object(os.path, 'exists',
                                         lambda _: False)
        mock_patcher.start()
        self.addCleanup(mock_patcher.stop)

    def test_relpath_config_not_found(self):
        self.config(api_paste_config='api-paste.ini')
        self.assertRaises(
            wsgi.ConfigNotFound,
            wsgi.Loader,
            self.conf
        )

    def test_asbpath_config_not_found(self):
        self.config(api_paste_config='/etc/openstack-srv/api-paste.ini')
        self.assertRaises(
            wsgi.ConfigNotFound,
            wsgi.Loader,
            self.conf
        )


class TestLoaderNormalFilesystem(WsgiTestCase):
    """Loader tests with normal filesystem (unmodified os.path module)."""

    _paste_config = """
[app:test_app]
use = egg:Paste#static
document_root = /tmp
    """

    def setUp(self):
        super(TestLoaderNormalFilesystem, self).setUp()
        self.paste_config = tempfile.NamedTemporaryFile(mode="w+t")
        self.paste_config.write(self._paste_config.lstrip())
        self.paste_config.seek(0)
        self.paste_config.flush()

        self.config(api_paste_config=self.paste_config.name)
        self.loader = wsgi.Loader(CONF)

    def test_config_found(self):
        self.assertEqual(self.paste_config.name, self.loader.config_path)

    def test_app_not_found(self):
        self.assertRaises(
            wsgi.PasteAppNotFound,
            self.loader.load_app,
            "nonexistent app",
        )

    def test_app_found(self):
        url_parser = self.loader.load_app("test_app")
        self.assertEqual("/tmp", url_parser.directory)

    def tearDown(self):
        self.paste_config.close()
        super(TestLoaderNormalFilesystem, self).tearDown()


class TestWSGIServer(WsgiTestCase):
    """WSGI server tests."""

    def setUp(self):
        super(TestWSGIServer, self).setUp()

    def test_no_app(self):
        server = wsgi.Server(self.conf, "test_app", None)
        self.assertEqual("test_app", server.name)

    def test_custom_max_header_line(self):
        self.config(max_header_line=4096)  # Default value is 16384
        wsgi.Server(self.conf, "test_custom_max_header_line", None)
        self.assertEqual(eventlet.wsgi.MAX_HEADER_LINE,
                         self.conf.max_header_line)

    def test_start_random_port(self):
        server = wsgi.Server(self.conf, "test_random_port", None,
                             host="127.0.0.1", port=0)
        server.start()
        self.assertNotEqual(0, server.port)
        server.stop()
        server.wait()

    @testtools.skipIf(not netutils.is_ipv6_enabled(), "no ipv6 support")
    def test_start_random_port_with_ipv6(self):
        server = wsgi.Server(self.conf, "test_random_port", None,
                             host="::1", port=0)
        server.start()
        self.assertEqual("::1", server.host)
        self.assertNotEqual(0, server.port)
        server.stop()
        server.wait()

    @testtools.skipIf(platform.mac_ver()[0] != '',
                      'SO_REUSEADDR behaves differently '
                      'on OSX, see bug 1436895')
    def test_socket_options_for_simple_server(self):
        # test normal socket options has set properly
        self.config(tcp_keepidle=500)
        server = wsgi.Server(self.conf, "test_socket_options", None,
                             host="127.0.0.1", port=0)
        server.start()
        sock = server.socket
        self.assertEqual(1, sock.getsockopt(socket.SOL_SOCKET,
                                            socket.SO_REUSEADDR))
        self.assertEqual(1, sock.getsockopt(socket.SOL_SOCKET,
                                            socket.SO_KEEPALIVE))
        if hasattr(socket, 'TCP_KEEPIDLE'):
            self.assertEqual(self.conf.tcp_keepidle,
                             sock.getsockopt(socket.IPPROTO_TCP,
                                             socket.TCP_KEEPIDLE))
        self.assertFalse(server._server.dead)
        server.stop()
        server.wait()
        self.assertTrue(server._server.dead)

    @testtools.skipIf(not hasattr(socket, "AF_UNIX"),
                      'UNIX sockets not supported')
    def test_server_with_unix_socket(self):
        socket_file = self.get_temp_file_path('sock')
        socket_mode = 0o644
        server = wsgi.Server(self.conf, "test_socket_options", None,
                             socket_family=socket.AF_UNIX,
                             socket_mode=socket_mode,
                             socket_file=socket_file)
        self.assertEqual(socket_file, server.socket.getsockname())
        self.assertEqual(socket_mode,
                         os.stat(socket_file).st_mode & 0o777)
        server.start()
        self.assertFalse(server._server.dead)
        server.stop()
        server.wait()
        self.assertTrue(server._server.dead)

    def test_server_pool_waitall(self):
        # test pools waitall method gets called while stopping server
        server = wsgi.Server(self.conf, "test_server", None, host="127.0.0.1")
        server.start()
        with mock.patch.object(server._pool,
                               'waitall') as mock_waitall:
            server.stop()
            server.wait()
            mock_waitall.assert_called_once_with()

    def test_uri_length_limit(self):
        eventlet.monkey_patch(os=False, thread=False)
        server = wsgi.Server(self.conf, "test_uri_length_limit", None,
                             host="127.0.0.1", max_url_len=16384, port=33337)
        server.start()
        self.assertFalse(server._server.dead)

        uri = "http://127.0.0.1:%d/%s" % (server.port, 10000 * 'x')
        resp = requests.get(uri, proxies={"http": ""})
        eventlet.sleep(0)
        self.assertNotEqual(requests.codes.REQUEST_URI_TOO_LARGE,
                            resp.status_code)

        uri = "http://127.0.0.1:%d/%s" % (server.port, 20000 * 'x')
        resp = requests.get(uri, proxies={"http": ""})
        eventlet.sleep(0)
        self.assertEqual(requests.codes.REQUEST_URI_TOO_LARGE,
                         resp.status_code)
        server.stop()
        server.wait()

    def test_reset_pool_size_to_default(self):
        server = wsgi.Server(self.conf, "test_resize", None,
                             host="127.0.0.1", max_url_len=16384)
        server.start()

        # Stopping the server, which in turn sets pool size to 0
        server.stop()
        self.assertEqual(0, server._pool.size)

        # Resetting pool size to default
        server.reset()
        server.start()
        self.assertEqual(CONF.wsgi_default_pool_size, server._pool.size)

    def test_client_socket_timeout(self):
        self.config(client_socket_timeout=5)

        # mocking eventlet spawn method to check it is called with
        # configured 'client_socket_timeout' value.
        with mock.patch.object(eventlet,
                               'spawn') as mock_spawn:
            server = wsgi.Server(self.conf, "test_app", None,
                                 host="127.0.0.1", port=0)
            server.start()
            _, kwargs = mock_spawn.call_args
            self.assertEqual(self.conf.client_socket_timeout,
                             kwargs['socket_timeout'])
            server.stop()

    def test_wsgi_keep_alive(self):
        self.config(wsgi_keep_alive=False)

        # mocking eventlet spawn method to check it is called with
        # configured 'wsgi_keep_alive' value.
        with mock.patch.object(eventlet,
                               'spawn') as mock_spawn:
            server = wsgi.Server(self.conf, "test_app", None,
                                 host="127.0.0.1", port=0)
            server.start()
            _, kwargs = mock_spawn.call_args
            self.assertEqual(self.conf.wsgi_keep_alive,
                             kwargs['keepalive'])
            server.stop()


class TestWSGIServerWithSSL(WsgiTestCase):
    """WSGI server with SSL tests."""

    def setUp(self):
        super(TestWSGIServerWithSSL, self).setUp()
        cert_file_name = os.path.join(SSL_CERT_DIR, 'certificate.crt')
        key_file_name = os.path.join(SSL_CERT_DIR, 'privatekey.key')
        eventlet.monkey_patch(os=False, thread=False)

        self.config(cert_file=cert_file_name,
                    key_file=key_file_name,
                    group=sslutils.config_section)

    @testtools.skipIf(six.PY3, "bug/1482633: test hangs on Python 3")
    def test_ssl_server(self):
        def test_app(env, start_response):
            start_response('200 OK', {})
            return ['PONG']

        fake_ssl_server = wsgi.Server(self.conf, "fake_ssl", test_app,
                                      host="127.0.0.1", port=0, use_ssl=True)
        fake_ssl_server.start()
        self.assertNotEqual(0, fake_ssl_server.port)

        response = requests.post(
            'https://127.0.0.1:%s/' % fake_ssl_server.port,
            verify=os.path.join(SSL_CERT_DIR, 'ca.crt'), data='PING')
        self.assertEqual('PONG', response.text)

        fake_ssl_server.stop()
        fake_ssl_server.wait()

    @testtools.skipIf(six.PY3, "bug/1482633: test hangs on Python 3")
    def test_two_servers(self):
        def test_app(env, start_response):
            start_response('200 OK', {})
            return ['PONG']

        fake_ssl_server = wsgi.Server(self.conf, "fake_ssl", test_app,
                                      host="127.0.0.1", port=0, use_ssl=True)
        fake_ssl_server.start()
        self.assertNotEqual(0, fake_ssl_server.port)

        fake_server = wsgi.Server(self.conf, "fake", test_app,
                                  host="127.0.0.1", port=0)
        fake_server.start()
        self.assertNotEqual(0, fake_server.port)

        response = requests.post(
            'https://127.0.0.1:%s/' % fake_ssl_server.port,
            verify=os.path.join(SSL_CERT_DIR, 'ca.crt'), data='PING')
        self.assertEqual('PONG', response.text)

        response = requests.post(
            'http://127.0.0.1:%s/' % fake_server.port, data='PING')
        self.assertEqual('PONG', response.text)

        fake_ssl_server.stop()
        fake_ssl_server.wait()

        fake_server.stop()
        fake_server.wait()

    @testtools.skipIf(platform.mac_ver()[0] != '',
                      'SO_REUSEADDR behaves differently '
                      'on OSX, see bug 1436895')
    @testtools.skipIf(six.PY3, "bug/1482633: test hangs on Python 3")
    def test_socket_options_for_ssl_server(self):
        # test normal socket options has set properly
        self.config(tcp_keepidle=500)
        server = wsgi.Server(self.conf, "test_socket_options", None,
                             host="127.0.0.1", port=0, use_ssl=True)
        server.start()
        sock = server.socket
        self.assertEqual(1, sock.getsockopt(socket.SOL_SOCKET,
                                            socket.SO_REUSEADDR))
        self.assertEqual(1, sock.getsockopt(socket.SOL_SOCKET,
                                            socket.SO_KEEPALIVE))
        if hasattr(socket, 'TCP_KEEPIDLE'):
            self.assertEqual(CONF.tcp_keepidle,
                             sock.getsockopt(socket.IPPROTO_TCP,
                                             socket.TCP_KEEPIDLE))
        server.stop()
        server.wait()

    @testtools.skipIf(not netutils.is_ipv6_enabled(), "no ipv6 support")
    @testtools.skipIf(six.PY3, "bug/1482633: test hangs on Python 3")
    @testtools.skip("using raw IPv6 addresses with SSL certs is broken")
    def test_app_using_ipv6_and_ssl(self):
        greetings = 'Hello, World!!!'

        @webob.dec.wsgify
        def hello_world(req):
            return greetings

        server = wsgi.Server(self.conf, "fake_ssl",
                             hello_world,
                             host="::1",
                             port=0,
                             use_ssl=True)

        server.start()

        response = requests.get('https://[::1]:%d/' % server.port,
                                verify=os.path.join(SSL_CERT_DIR, 'ca.crt'))
        self.assertEqual(greetings, response.text)

        server.stop()
        server.wait()
