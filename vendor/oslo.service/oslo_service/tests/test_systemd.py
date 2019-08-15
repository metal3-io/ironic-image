# Copyright 2014 Red Hat, Inc.
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

import os
import socket

import mock
from oslotest import base as test_base

from oslo_service import systemd


class SystemdTestCase(test_base.BaseTestCase):
    """Test case for Systemd service readiness."""

    def test__abstractify(self):
        sock_name = '@fake_socket'
        res = systemd._abstractify(sock_name)
        self.assertEqual('\0{0}'.format(sock_name[1:]), res)

    @mock.patch.object(os, 'getenv', return_value='@fake_socket')
    def _test__sd_notify(self, getenv_mock, unset_env=False):
        self.ready = False
        self.closed = False

        class FakeSocket(object):
            def __init__(self, family, type):
                pass

            def connect(fs, socket):
                pass

            def close(fs):
                self.closed = True

            def sendall(fs, data):
                if data == b'READY=1':
                    self.ready = True

        with mock.patch.object(socket, 'socket', new=FakeSocket):
            if unset_env:
                systemd.notify_once()
            else:
                systemd.notify()

            self.assertTrue(self.ready)
            self.assertTrue(self.closed)

    def test_notify(self):
        self._test__sd_notify()

    def test_notify_once(self):
        os.environ['NOTIFY_SOCKET'] = '@fake_socket'
        self._test__sd_notify(unset_env=True)
        self.assertRaises(KeyError, os.environ.__getitem__, 'NOTIFY_SOCKET')

    @mock.patch("socket.socket")
    def test_onready(self, sock_mock):
        recv_results = [b'READY=1', '', socket.timeout]
        expected_results = [0, 1, 2]
        for recv, expected in zip(recv_results, expected_results):
            if recv == socket.timeout:
                sock_mock.return_value.recv.side_effect = recv
            else:
                sock_mock.return_value.recv.return_value = recv
            actual = systemd.onready('@fake_socket', 1)
            self.assertEqual(expected, actual)
