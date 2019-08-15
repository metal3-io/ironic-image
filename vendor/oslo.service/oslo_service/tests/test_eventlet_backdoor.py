# Copyright 2010 United States Government as represented by the
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

"""
Unit Tests for eventlet backdoor
"""
import errno
import os
import socket

import eventlet
import mock

from oslo_service import eventlet_backdoor
from oslo_service.tests import base


class BackdoorSocketPathTest(base.ServiceBaseTestCase):

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_path(self, listen_mock, spawn_mock):
        self.config(backdoor_socket="/tmp/my_special_socket")
        listen_mock.side_effect = mock.Mock()
        path = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual("/tmp/my_special_socket", path)

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_path_with_format_string(self, listen_mock, spawn_mock):
        self.config(backdoor_socket="/tmp/my_special_socket-{pid}")
        listen_mock.side_effect = mock.Mock()
        path = eventlet_backdoor.initialize_if_enabled(self.conf)
        expected_path = "/tmp/my_special_socket-{}".format(os.getpid())
        self.assertEqual(expected_path, path)

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_path_with_broken_format_string(self, listen_mock,
                                                     spawn_mock):
        broken_socket_paths = [
            "/tmp/my_special_socket-{}",
            "/tmp/my_special_socket-{broken",
            "/tmp/my_special_socket-{broken}",
        ]
        for socket_path in broken_socket_paths:
            self.config(backdoor_socket=socket_path)
            listen_mock.side_effect = mock.Mock()
            path = eventlet_backdoor.initialize_if_enabled(self.conf)
            self.assertEqual(socket_path, path)

    @mock.patch.object(os, 'unlink')
    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_path_already_exists(self, listen_mock,
                                          spawn_mock, unlink_mock):
        self.config(backdoor_socket="/tmp/my_special_socket")
        sock = mock.Mock()
        listen_mock.side_effect = [socket.error(errno.EADDRINUSE, ''), sock]
        path = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual("/tmp/my_special_socket", path)
        unlink_mock.assert_called_with("/tmp/my_special_socket")

    @mock.patch.object(os, 'unlink')
    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_path_already_exists_and_gone(self, listen_mock,
                                                   spawn_mock, unlink_mock):
        self.config(backdoor_socket="/tmp/my_special_socket")
        sock = mock.Mock()
        listen_mock.side_effect = [socket.error(errno.EADDRINUSE, ''), sock]
        unlink_mock.side_effect = OSError(errno.ENOENT, '')
        path = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual("/tmp/my_special_socket", path)
        unlink_mock.assert_called_with("/tmp/my_special_socket")

    @mock.patch.object(os, 'unlink')
    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_path_already_exists_and_not_gone(self, listen_mock,
                                                       spawn_mock,
                                                       unlink_mock):
        self.config(backdoor_socket="/tmp/my_special_socket")
        listen_mock.side_effect = socket.error(errno.EADDRINUSE, '')
        unlink_mock.side_effect = OSError(errno.EPERM, '')
        self.assertRaises(OSError, eventlet_backdoor.initialize_if_enabled,
                          self.conf)

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_path_no_perms(self, listen_mock, spawn_mock):
        self.config(backdoor_socket="/tmp/my_special_socket")
        listen_mock.side_effect = socket.error(errno.EPERM, '')
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled,
                          self.conf)


class BackdoorPortTest(base.ServiceBaseTestCase):

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_port(self, listen_mock, spawn_mock):
        self.config(backdoor_port=1234)
        sock = mock.Mock()
        sock.getsockname.return_value = ('127.0.0.1', 1234)
        listen_mock.return_value = sock
        port = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual(1234, port)

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_port_inuse(self, listen_mock, spawn_mock):
        self.config(backdoor_port=2345)
        listen_mock.side_effect = socket.error(errno.EADDRINUSE, '')
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled, self.conf)

    @mock.patch.object(eventlet, 'spawn')
    def test_backdoor_port_range_inuse(self, spawn_mock):
        self.config(backdoor_port='8800:8801')
        port = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual(8800, port)
        port = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual(8801, port)

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_port_range(self, listen_mock, spawn_mock):
        self.config(backdoor_port='8800:8899')
        sock = mock.Mock()
        sock.getsockname.return_value = ('127.0.0.1', 8800)
        listen_mock.return_value = sock
        port = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual(8800, port)

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_port_range_one_inuse(self, listen_mock, spawn_mock):
        self.config(backdoor_port='8800:8900')
        sock = mock.Mock()
        sock.getsockname.return_value = ('127.0.0.1', 8801)
        listen_mock.side_effect = [socket.error(errno.EADDRINUSE, ''), sock]
        port = eventlet_backdoor.initialize_if_enabled(self.conf)
        self.assertEqual(8801, port)

    @mock.patch.object(eventlet, 'spawn')
    @mock.patch.object(eventlet, 'listen')
    def test_backdoor_port_range_all_inuse(self, listen_mock, spawn_mock):
        self.config(backdoor_port='8800:8899')
        side_effects = []
        for i in range(8800, 8900):
            side_effects.append(socket.error(errno.EADDRINUSE, ''))
        listen_mock.side_effect = side_effects
        self.assertRaises(socket.error,
                          eventlet_backdoor.initialize_if_enabled, self.conf)

    def test_backdoor_port_reverse_range(self):
        self.config(backdoor_port='8888:7777')
        self.assertRaises(eventlet_backdoor.EventletBackdoorConfigValueError,
                          eventlet_backdoor.initialize_if_enabled, self.conf)

    def test_backdoor_port_bad(self):
        self.config(backdoor_port='abc')
        self.assertRaises(eventlet_backdoor.EventletBackdoorConfigValueError,
                          eventlet_backdoor.initialize_if_enabled, self.conf)
