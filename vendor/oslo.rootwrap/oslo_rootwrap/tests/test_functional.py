# Copyright (c) 2014 Mirantis Inc.
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

import contextlib
import io
import logging
import os
import pwd
import shutil
import signal
import sys
import threading
import time

try:
    import eventlet
except ImportError:
    eventlet = None

import fixtures
import mock
import six
import testtools
from testtools import content

from oslo_rootwrap import client
from oslo_rootwrap import cmd
from oslo_rootwrap import subprocess
from oslo_rootwrap.tests import run_daemon


class _FunctionalBase(object):
    def setUp(self):
        super(_FunctionalBase, self).setUp()
        tmpdir = self.useFixture(fixtures.TempDir()).path
        self.config_file = os.path.join(tmpdir, 'rootwrap.conf')
        self.later_cmd = os.path.join(tmpdir, 'later_install_cmd')
        filters_dir = os.path.join(tmpdir, 'filters.d')
        filters_file = os.path.join(tmpdir, 'filters.d', 'test.filters')
        os.mkdir(filters_dir)
        with open(self.config_file, 'w') as f:
            f.write("""[DEFAULT]
filters_path=%s
daemon_timeout=10
exec_dirs=/bin""" % (filters_dir,))
        with open(filters_file, 'w') as f:
            f.write("""[Filters]
echo: CommandFilter, /bin/echo, root
cat: CommandFilter, /bin/cat, root
sh: CommandFilter, /bin/sh, root
id: CommandFilter, /usr/bin/id, nobody
unknown_cmd: CommandFilter, /unknown/unknown_cmd, root
later_install_cmd: CommandFilter, %s, root
""" % self.later_cmd)

    def _test_run_once(self, expect_byte=True):
        code, out, err = self.execute(['echo', 'teststr'])
        self.assertEqual(0, code)
        if expect_byte:
            expect_out = b'teststr\n'
            expect_err = b''
        else:
            expect_out = 'teststr\n'
            expect_err = ''
        self.assertEqual(expect_out, out)
        self.assertEqual(expect_err, err)

    def _test_run_with_stdin(self, expect_byte=True):
        code, out, err = self.execute(['cat'], stdin=b'teststr')
        self.assertEqual(0, code)
        if expect_byte:
            expect_out = b'teststr'
            expect_err = b''
        else:
            expect_out = 'teststr'
            expect_err = ''
        self.assertEqual(expect_out, out)
        self.assertEqual(expect_err, err)

    def test_run_command_not_found(self):
        code, out, err = self.execute(['unknown_cmd'])
        self.assertEqual(cmd.RC_NOEXECFOUND, code)

    def test_run_unauthorized_command(self):
        code, out, err = self.execute(['unauthorized_cmd'])
        self.assertEqual(cmd.RC_UNAUTHORIZED, code)

    def test_run_as(self):
        if os.getuid() != 0:
            self.skip('Test requires root (for setuid)')

        # Should run as 'nobody'
        code, out, err = self.execute(['id', '-u'])
        self.assertEqual('%s\n' % pwd.getpwnam('nobody').pw_uid, out)

        # Should run as 'root'
        code, out, err = self.execute(['sh', '-c', 'id -u'])
        self.assertEqual('0\n', out)


class RootwrapTest(_FunctionalBase, testtools.TestCase):
    def setUp(self):
        super(RootwrapTest, self).setUp()
        self.cmd = [
            sys.executable, '-c',
            'from oslo_rootwrap import cmd; cmd.main()',
            self.config_file]

    def execute(self, cmd, stdin=None):
        proc = subprocess.Popen(
            self.cmd + cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate(stdin)
        self.addDetail('stdout',
                       content.text_content(out.decode('utf-8', 'replace')))
        self.addDetail('stderr',
                       content.text_content(err.decode('utf-8', 'replace')))
        return proc.returncode, out, err

    def test_run_once(self):
        self._test_run_once(expect_byte=True)

    def test_run_with_stdin(self):
        self._test_run_with_stdin(expect_byte=True)


class RootwrapDaemonTest(_FunctionalBase, testtools.TestCase):
    def assert_unpatched(self):
        # We need to verify that these tests are run without eventlet patching
        if eventlet and eventlet.patcher.is_monkey_patched('socket'):
            self.fail("Standard library should not be patched by eventlet"
                      " for this test")

    def setUp(self):
        self.assert_unpatched()

        super(RootwrapDaemonTest, self).setUp()

        # Collect daemon logs
        daemon_log = io.BytesIO()
        p = mock.patch('oslo_rootwrap.subprocess.Popen',
                       run_daemon.forwarding_popen(daemon_log))
        p.start()
        self.addCleanup(p.stop)

        # Collect client logs
        client_log = six.StringIO()
        handler = logging.StreamHandler(client_log)
        log_format = run_daemon.log_format.replace('+', ' ')
        handler.setFormatter(logging.Formatter(log_format))
        logger = logging.getLogger('oslo_rootwrap')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        self.addCleanup(logger.removeHandler, handler)

        # Add all logs as details
        @self.addCleanup
        def add_logs():
            self.addDetail('daemon_log', content.Content(
                content.UTF8_TEXT,
                lambda: [daemon_log.getvalue()]))
            self.addDetail('client_log', content.Content(
                content.UTF8_TEXT,
                lambda: [client_log.getvalue().encode('utf-8')]))

        # Create client
        self.client = client.Client([
            sys.executable, run_daemon.__file__,
            self.config_file])

        # _finalize is set during Client.execute()
        @self.addCleanup
        def finalize_client():
            if self.client._initialized:
                self.client._finalize()

        self.execute = self.client.execute

    def test_run_once(self):
        self._test_run_once(expect_byte=False)

    def test_run_with_stdin(self):
        self._test_run_with_stdin(expect_byte=False)

    def test_run_with_later_install_cmd(self):
        code, out, err = self.execute(['later_install_cmd'])
        self.assertEqual(cmd.RC_NOEXECFOUND, code)
        # Install cmd and try again
        shutil.copy('/bin/echo', self.later_cmd)
        code, out, err = self.execute(['later_install_cmd'])
        # Expect successfully run the cmd
        self.assertEqual(0, code)

    def test_daemon_ressurection(self):
        # Let the client start a daemon
        self.execute(['cat'])
        # Make daemon go away
        os.kill(self.client._process.pid, signal.SIGTERM)
        # Expect client to successfully restart daemon and run simple request
        self.test_run_once()

    def test_daemon_timeout(self):
        # Let the client start a daemon
        self.execute(['echo'])
        # Make daemon timeout
        with mock.patch.object(self.client, '_restart') as restart:
            time.sleep(15)
            self.execute(['echo'])
            restart.assert_called_once()

    def _exec_thread(self, fifo_path):
        try:
            # Run a shell script that signals calling process through FIFO and
            # then hangs around for 1 sec
            self._thread_res = self.execute([
                'sh', '-c', 'echo > "%s"; sleep 1; echo OK' % fifo_path])
        except Exception as e:
            self._thread_res = e

    def test_graceful_death(self):
        # Create a fifo in a temporary dir
        tmpdir = self.useFixture(fixtures.TempDir()).path
        fifo_path = os.path.join(tmpdir, 'fifo')
        os.mkfifo(fifo_path)
        # Start daemon
        self.execute(['cat'])
        # Begin executing shell script
        t = threading.Thread(target=self._exec_thread, args=(fifo_path,))
        t.start()
        # Wait for shell script to actually start
        with open(fifo_path) as f:
            f.readline()
        # Gracefully kill daemon process
        os.kill(self.client._process.pid, signal.SIGTERM)
        # Expect daemon to wait for our request to finish
        t.join()
        if isinstance(self._thread_res, Exception):
            raise self._thread_res  # Python 3 will even provide nice traceback
        code, out, err = self._thread_res
        self.assertEqual(0, code)
        self.assertEqual('OK\n', out)
        self.assertEqual('', err)

    @contextlib.contextmanager
    def _test_daemon_cleanup(self):
        # Start a daemon
        self.execute(['cat'])
        socket_path = self.client._manager._address
        # Stop it one way or another
        yield
        process = self.client._process
        stop = threading.Event()

        # Start background thread that would kill process in 1 second if it
        # doesn't die by then
        def sleep_kill():
            stop.wait(1)
            if not stop.is_set():
                os.kill(process.pid, signal.SIGKILL)
        threading.Thread(target=sleep_kill).start()
        # Wait for process to finish one way or another
        self.client._process.wait()
        # Notify background thread that process is dead (no need to kill it)
        stop.set()
        # Fail if the process got killed by the background thread
        self.assertNotEqual(-signal.SIGKILL, process.returncode,
                            "Server haven't stopped in one second")
        # Verify that socket is deleted
        self.assertFalse(os.path.exists(socket_path),
                         "Server didn't remove its temporary directory")

    def test_daemon_cleanup_client(self):
        # Run _test_daemon_cleanup stopping daemon as Client instance would
        # normally do
        with self._test_daemon_cleanup():
            self.client._finalize()

    def test_daemon_cleanup_signal(self):
        # Run _test_daemon_cleanup stopping daemon with SIGTERM signal
        with self._test_daemon_cleanup():
            os.kill(self.client._process.pid, signal.SIGTERM)
