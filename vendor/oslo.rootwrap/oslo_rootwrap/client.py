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

import logging
from multiprocessing import managers
from multiprocessing import util as mp_util
import threading
import weakref

import oslo_rootwrap
from oslo_rootwrap import daemon
from oslo_rootwrap import jsonrpc
from oslo_rootwrap import subprocess

if oslo_rootwrap._patched_socket:
    # We have to use slow version of recvall with eventlet because of a bug in
    # GreenSocket.recv_into:
    # https://bitbucket.org/eventlet/eventlet/pull-request/41
    # This check happens here instead of jsonrpc to avoid importing eventlet
    # from daemon code that is run with root privileges.
    jsonrpc.JsonConnection.recvall = jsonrpc.JsonConnection._recvall_slow

try:
    finalize = weakref.finalize
except AttributeError:
    def finalize(obj, func, *args, **kwargs):
        return mp_util.Finalize(obj, func, args=args, kwargs=kwargs,
                                exitpriority=0)

ClientManager = daemon.get_manager_class()
LOG = logging.getLogger(__name__)


class Client(object):
    def __init__(self, rootwrap_daemon_cmd):
        self._start_command = rootwrap_daemon_cmd
        self._initialized = False
        self._need_restart = False
        self._mutex = threading.Lock()
        self._manager = None
        self._proxy = None
        self._process = None
        self._finalize = None
        # This is for eventlet compatibility. multiprocessing stores
        # daemon connection in ForkAwareLocal, so this won't be
        # needed with the threading module.
        self._exec_sem = threading.Lock()

    def _initialize(self):
        if self._process is not None and self._process.poll() is not None:
            LOG.warning("Leaving behind already spawned process with pid %d, "
                        "root should kill it if it's still there (I can't)",
                        self._process.pid)

        process_obj = subprocess.Popen(self._start_command,
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       close_fds=True)
        LOG.debug("Popen for %s command has been instantiated",
                  self._start_command)

        self._process = process_obj
        socket_path = process_obj.stdout.readline()[:-1]
        # For Python 3 we need to convert bytes to str here
        if not isinstance(socket_path, str):
            socket_path = socket_path.decode('utf-8')
        authkey = process_obj.stdout.read(32)
        if process_obj.poll() is not None:
            stderr = process_obj.stderr.read()
            # NOTE(yorik-sar): don't expose stdout here
            raise Exception("Failed to spawn rootwrap process.\nstderr:\n%s" %
                            (stderr,))
        LOG.info("Spawned new rootwrap daemon process with pid=%d",
                 process_obj.pid)
        self._manager = ClientManager(socket_path, authkey)
        self._manager.connect()
        self._proxy = self._manager.rootwrap()
        self._finalize = finalize(self, self._shutdown, self._process,
                                  self._manager)
        self._initialized = True

    @staticmethod
    def _shutdown(process, manager, JsonClient=jsonrpc.JsonClient):
        # Storing JsonClient in arguments because globals are set to None
        # before executing atexit routines in Python 2.x
        if process.poll() is None:
            LOG.info('Stopping rootwrap daemon process with pid=%s',
                     process.pid)
            try:
                manager.rootwrap().shutdown()
            except (EOFError, IOError):
                pass  # assume it is dead already
            # We might want to wait for process to exit or kill it, but we
            # can't provide sane timeout on 2.x and we most likely don't have
            # permisions to do so
        # Invalidate manager's state so that proxy won't try to do decref
        manager._state.value = managers.State.SHUTDOWN

    def _ensure_initialized(self):
        with self._mutex:
            if not self._initialized:
                self._initialize()

    def _restart(self, proxy):
        with self._mutex:
            if not self._initialized:
                raise AssertionError("Client should be initialized.")
            # Verify if someone has already restarted this.
            if self._proxy is proxy:
                self._finalize()
                self._manager = None
                self._proxy = None
                self._initialized = False
                self._initialize()
                self._need_restart = False
            return self._proxy

    def _run_one_command(self, proxy, cmd, stdin):
        """Wrap proxy.run_one_command, setting _need_restart on an exception.

        Usually it should be enough to drain stale data on socket
        rather than to restart, but we cannot do draining easily.
        """
        try:
            _need_restart = True
            res = proxy.run_one_command(cmd, stdin)
            _need_restart = False
            return res
        finally:
            if _need_restart:
                self._need_restart = True

    def execute(self, cmd, stdin=None):
        with self._exec_sem:
            self._ensure_initialized()
            proxy = self._proxy
            retry = False
            if self._need_restart:
                proxy = self._restart(proxy)
            try:
                res = self._run_one_command(proxy, cmd, stdin)
            except (EOFError, IOError):
                retry = True
            # res can be None if we received final None sent by dying
            # server thread instead of response to our
            # request. Process is most likely to be dead at this
            # point.
            if retry or res is None:
                proxy = self._restart(proxy)
                res = self._run_one_command(proxy, cmd, stdin)
        return res
