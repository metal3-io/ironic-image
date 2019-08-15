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
Unit Tests for service class
"""

from __future__ import print_function

import logging
import multiprocessing
import os
import signal
import socket
import time
import traceback

import eventlet
from eventlet import event
import mock
from oslotest import base as test_base

from oslo_service import service
from oslo_service.tests import base
from oslo_service.tests import eventlet_service


LOG = logging.getLogger(__name__)


class ExtendedService(service.Service):
    def test_method(self):
        return 'service'


class ServiceManagerTestCase(test_base.BaseTestCase):
    """Test cases for Services."""
    def test_override_manager_method(self):
        serv = ExtendedService()
        serv.start()
        self.assertEqual('service', serv.test_method())


class ServiceWithTimer(service.Service):
    def __init__(self, ready_event=None):
        super(ServiceWithTimer, self).__init__()
        self.ready_event = ready_event

    def start(self):
        super(ServiceWithTimer, self).start()
        self.timer_fired = 0
        self.tg.add_timer(1, self.timer_expired)

    def wait(self):
        if self.ready_event:
            self.ready_event.set()
        super(ServiceWithTimer, self).wait()

    def timer_expired(self):
        self.timer_fired = self.timer_fired + 1


class ServiceCrashOnStart(ServiceWithTimer):
    def start(self):
        super(ServiceCrashOnStart, self).start()
        raise ValueError


class ServiceTestBase(base.ServiceBaseTestCase):
    """A base class for ServiceLauncherTest and ServiceRestartTest."""

    def _spawn_service(self,
                       workers=1,
                       service_maker=None,
                       launcher_maker=None):
        self.workers = workers
        pid = os.fork()
        if pid == 0:
            os.setsid()
            # NOTE(johannes): We can't let the child processes exit back
            # into the unit test framework since then we'll have multiple
            # processes running the same tests (and possibly forking more
            # processes that end up in the same situation). So we need
            # to catch all exceptions and make sure nothing leaks out, in
            # particular SystemExit, which is raised by sys.exit(). We use
            # os._exit() which doesn't have this problem.
            status = 0
            try:
                serv = service_maker() if service_maker else ServiceWithTimer()
                if launcher_maker:
                    launcher = launcher_maker()
                    launcher.launch_service(serv, workers=workers)
                else:
                    launcher = service.launch(self.conf, serv, workers=workers)
                status = launcher.wait()
            except SystemExit as exc:
                status = exc.code
            except BaseException:
                # We need to be defensive here too
                try:
                    traceback.print_exc()
                except BaseException:
                    print("Couldn't print traceback")
                status = 2
            # Really exit
            os._exit(status or 0)
        return pid

    def _wait(self, cond, timeout):
        start = time.time()
        while not cond():
            if time.time() - start > timeout:
                break
            time.sleep(.1)

    def setUp(self):
        super(ServiceTestBase, self).setUp()
        # NOTE(markmc): ConfigOpts.log_opt_values() uses CONF.config-file
        self.conf(args=[], default_config_files=[])
        self.addCleanup(self.conf.reset)
        self.addCleanup(self._reap_pid)
        self.pid = 0

    def _reap_pid(self):
        if self.pid:
            # Make sure all processes are stopped
            os.kill(self.pid, signal.SIGTERM)

            # Make sure we reap our test process
            self._reap_test()

    def _reap_test(self):
        pid, status = os.waitpid(self.pid, 0)
        self.pid = None
        return status


class ServiceLauncherTest(ServiceTestBase):
    """Originally from nova/tests/integrated/test_multiprocess_api.py."""

    def _spawn(self):
        self.pid = self._spawn_service(workers=2)

        # Wait at most 10 seconds to spawn workers
        cond = lambda: self.workers == len(self._get_workers())
        timeout = 10
        self._wait(cond, timeout)

        workers = self._get_workers()
        self.assertEqual(len(workers), self.workers)
        return workers

    def _get_workers(self):
        f = os.popen('ps ax -o pid,ppid,command')
        # Skip ps header
        f.readline()

        processes = [tuple(int(p) for p in l.strip().split()[:2])
                     for l in f]
        return [p for p, pp in processes if pp == self.pid]

    def test_killed_worker_recover(self):
        start_workers = self._spawn()

        # kill one worker and check if new worker can come up
        LOG.info('pid of first child is %s' % start_workers[0])
        os.kill(start_workers[0], signal.SIGTERM)

        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers != self._get_workers()
        timeout = 5
        self._wait(cond, timeout)

        # Make sure worker pids don't match
        end_workers = self._get_workers()
        LOG.info('workers: %r' % end_workers)
        self.assertNotEqual(start_workers, end_workers)

    def _terminate_with_signal(self, sig):
        self._spawn()

        os.kill(self.pid, sig)

        # Wait at most 5 seconds to kill all workers
        cond = lambda: not self._get_workers()
        timeout = 5
        self._wait(cond, timeout)

        workers = self._get_workers()
        LOG.info('workers: %r' % workers)
        self.assertFalse(workers, 'No OS processes left.')

    def test_terminate_sigkill(self):
        self._terminate_with_signal(signal.SIGKILL)
        status = self._reap_test()
        self.assertTrue(os.WIFSIGNALED(status))
        self.assertEqual(signal.SIGKILL, os.WTERMSIG(status))

    def test_terminate_sigterm(self):
        self._terminate_with_signal(signal.SIGTERM)
        status = self._reap_test()
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(0, os.WEXITSTATUS(status))

    def test_crashed_service(self):
        service_maker = lambda: ServiceCrashOnStart()
        self.pid = self._spawn_service(service_maker=service_maker)
        status = self._reap_test()
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(1, os.WEXITSTATUS(status))

    def test_child_signal_sighup(self):
        start_workers = self._spawn()

        os.kill(start_workers[0], signal.SIGHUP)
        # Wait at most 5 seconds to respawn a worker
        cond = lambda: start_workers != self._get_workers()
        timeout = 5
        self._wait(cond, timeout)

        # Make sure worker pids match
        end_workers = self._get_workers()
        LOG.info('workers: %r' % end_workers)
        self.assertEqual(start_workers, end_workers)

    def test_parent_signal_sighup(self):
        start_workers = self._spawn()

        os.kill(self.pid, signal.SIGHUP)

        def cond():
            workers = self._get_workers()
            return (len(workers) == len(start_workers) and
                    not set(start_workers).intersection(workers))

        # Wait at most 5 seconds to respawn a worker
        timeout = 10
        self._wait(cond, timeout)
        self.assertTrue(cond())


class ServiceRestartTest(ServiceTestBase):

    def _spawn(self):
        ready_event = multiprocessing.Event()
        service_maker = lambda: ServiceWithTimer(ready_event=ready_event)
        self.pid = self._spawn_service(service_maker=service_maker)
        return ready_event

    def test_service_restart(self):
        ready = self._spawn()

        timeout = 5
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never became ready')
        ready.clear()

        os.kill(self.pid, signal.SIGHUP)
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never back after SIGHUP')

    def test_terminate_sigterm(self):
        ready = self._spawn()
        timeout = 5
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never became ready')

        os.kill(self.pid, signal.SIGTERM)

        status = self._reap_test()
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(0, os.WEXITSTATUS(status))

    def test_mutate_hook_service_launcher(self):
        """Test mutate_config_files is called by ServiceLauncher on SIGHUP.

        Not using _spawn_service because ServiceLauncher doesn't fork and it's
        simplest to stay all in one process.
        """
        mutate = multiprocessing.Event()
        self.conf.register_mutate_hook(lambda c, f: mutate.set())
        launcher = service.launch(
            self.conf, ServiceWithTimer(), restart_method='mutate')

        self.assertFalse(mutate.is_set(), "Hook was called too early")
        launcher.restart()
        self.assertTrue(mutate.is_set(), "Hook wasn't called")

    def test_mutate_hook_process_launcher(self):
        """Test mutate_config_files is called by ProcessLauncher on SIGHUP.

        Forks happen in _spawn_service and ProcessLauncher. So we get three
        tiers of processes, the top tier being the test process. self.pid
        refers to the middle tier, which represents our application. Both
        service_maker and launcher_maker execute in the middle tier. The bottom
        tier is the workers.

        The behavior we want is that when the application (middle tier)
        receives a SIGHUP, it catches that, calls mutate_config_files and
        relaunches all the workers. This causes them to inherit the mutated
        config.
        """
        mutate = multiprocessing.Event()
        ready = multiprocessing.Event()

        def service_maker():
            self.conf.register_mutate_hook(lambda c, f: mutate.set())
            return ServiceWithTimer(ready)

        def launcher_maker():
            return service.ProcessLauncher(self.conf, restart_method='mutate')

        self.pid = self._spawn_service(1, service_maker, launcher_maker)

        timeout = 5
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never became ready')
        ready.clear()

        self.assertFalse(mutate.is_set(), "Hook was called too early")
        os.kill(self.pid, signal.SIGHUP)
        ready.wait(timeout)
        self.assertTrue(ready.is_set(), 'Service never back after SIGHUP')
        self.assertTrue(mutate.is_set(), "Hook wasn't called")


class _Service(service.Service):
    def __init__(self):
        super(_Service, self).__init__()
        self.init = event.Event()
        self.cleaned_up = False

    def start(self):
        self.init.send()

    def stop(self):
        self.cleaned_up = True
        super(_Service, self).stop()


class LauncherTest(base.ServiceBaseTestCase):

    def test_graceful_shutdown(self):
        # test that services are given a chance to clean up:
        svc = _Service()

        launcher = service.launch(self.conf, svc)
        # wait on 'init' so we know the service had time to start:
        svc.init.wait()

        launcher.stop()
        self.assertTrue(svc.cleaned_up)

        # make sure stop can be called more than once.  (i.e. play nice with
        # unit test fixtures in nova bug #1199315)
        launcher.stop()

    @mock.patch('oslo_service.service.ServiceLauncher.launch_service')
    def _test_launch_single(self, workers, mock_launch):
        svc = service.Service()
        service.launch(self.conf, svc, workers=workers)
        mock_launch.assert_called_with(svc, workers=workers)

    def test_launch_none(self):
        self._test_launch_single(None)

    def test_launch_one_worker(self):
        self._test_launch_single(1)

    def test_launch_invalid_workers_number(self):
        svc = service.Service()
        for num_workers in [0, -1]:
            self.assertRaises(ValueError, service.launch, self.conf,
                              svc, num_workers)
        for num_workers in ["0", "a", "1"]:
            self.assertRaises(TypeError, service.launch, self.conf,
                              svc, num_workers)

    @mock.patch('signal.alarm')
    @mock.patch('oslo_service.service.ProcessLauncher.launch_service')
    def test_multiple_worker(self, mock_launch, alarm_mock):
        svc = service.Service()
        service.launch(self.conf, svc, workers=3)
        mock_launch.assert_called_with(svc, workers=3)

    def test_launch_wrong_service_base_class(self):
        # check that services that do not subclass service.ServiceBase
        # can not be launched.
        svc = mock.Mock()
        self.assertRaises(TypeError, service.launch, self.conf, svc)

    @mock.patch('signal.alarm')
    @mock.patch("oslo_service.service.Services.add")
    @mock.patch("oslo_service.eventlet_backdoor.initialize_if_enabled")
    def test_check_service_base(self, initialize_if_enabled_mock,
                                services_mock,
                                alarm_mock):
        initialize_if_enabled_mock.return_value = None
        launcher = service.Launcher(self.conf)
        serv = _Service()
        launcher.launch_service(serv)

    @mock.patch('signal.alarm')
    @mock.patch("oslo_service.service.Services.add")
    @mock.patch("oslo_service.eventlet_backdoor.initialize_if_enabled")
    def test_check_service_base_fails(self, initialize_if_enabled_mock,
                                      services_mock,
                                      alarm_mock):
        initialize_if_enabled_mock.return_value = None
        launcher = service.Launcher(self.conf)

        class FooService(object):
            def __init__(self):
                pass
        serv = FooService()
        self.assertRaises(TypeError, launcher.launch_service, serv)


class ProcessLauncherTest(base.ServiceBaseTestCase):

    @mock.patch('signal.alarm')
    @mock.patch("signal.signal")
    def test_stop(self, signal_mock, alarm_mock):
        signal_mock.SIGTERM = 15
        launcher = service.ProcessLauncher(self.conf)
        self.assertTrue(launcher.running)

        pid_nums = [22, 222]
        fakeServiceWrapper = service.ServiceWrapper(service.Service(), 1)
        launcher.children = {pid_nums[0]: fakeServiceWrapper,
                             pid_nums[1]: fakeServiceWrapper}
        with mock.patch('oslo_service.service.os.kill') as mock_kill:
            with mock.patch.object(launcher, '_wait_child') as _wait_child:

                def fake_wait_child():
                    pid = pid_nums.pop()
                    return launcher.children.pop(pid)

                _wait_child.side_effect = fake_wait_child
                with mock.patch('oslo_service.service.Service.stop') as \
                        mock_service_stop:
                    mock_service_stop.side_effect = lambda: None
                    launcher.stop()

        self.assertFalse(launcher.running)
        self.assertFalse(launcher.children)
        mock_kill.assert_has_calls([mock.call(222, signal_mock.SIGTERM),
                                    mock.call(22, signal_mock.SIGTERM)],
                                   any_order=True)
        self.assertEqual(2, mock_kill.call_count)
        mock_service_stop.assert_called_once_with()

    def test__handle_signal(self):
        signal_handler = service.SignalHandler()
        signal_handler.clear()
        self.assertEqual(0,
                         len(signal_handler._signal_handlers[signal.SIGTERM]))
        call_1, call_2 = mock.Mock(), mock.Mock()
        signal_handler.add_handler('SIGTERM', call_1)
        signal_handler.add_handler('SIGTERM', call_2)
        self.assertEqual(2,
                         len(signal_handler._signal_handlers[signal.SIGTERM]))
        signal_handler._handle_signal(signal.SIGTERM, 'test')
        # execute pending eventlet callbacks
        time.sleep(0)
        for m in signal_handler._signal_handlers[signal.SIGTERM]:
            m.assert_called_once_with(signal.SIGTERM, 'test')
        signal_handler.clear()

    @mock.patch('sys.version_info', (3, 5))
    def test_setup_signal_interruption_no_select_poll(self):
        # NOTE(claudiub): SignalHandler is a singleton, which means that it
        # might already be initialized. We need to clear to clear the cache
        # in order to prevent race conditions between tests.
        service.SignalHandler.__class__._instances.clear()
        with mock.patch('eventlet.patcher.original',
                        return_value=object()) as get_original:
            signal_handler = service.SignalHandler()
            get_original.assert_called_with('select')
        self.addCleanup(service.SignalHandler.__class__._instances.clear)
        self.assertFalse(
            signal_handler._SignalHandler__force_interrupt_on_signal)

    @mock.patch('sys.version_info', (3, 5))
    def test_setup_signal_interruption_select_poll(self):
        # NOTE(claudiub): SignalHandler is a singleton, which means that it
        # might already be initialized. We need to clear to clear the cache
        # in order to prevent race conditions between tests.
        service.SignalHandler.__class__._instances.clear()
        signal_handler = service.SignalHandler()
        self.addCleanup(service.SignalHandler.__class__._instances.clear)
        self.assertTrue(
            signal_handler._SignalHandler__force_interrupt_on_signal)

    @mock.patch('signal.alarm')
    @mock.patch("os.kill")
    @mock.patch("oslo_service.service.ProcessLauncher.stop")
    @mock.patch("oslo_service.service.ProcessLauncher._respawn_children")
    @mock.patch("oslo_service.service.ProcessLauncher.handle_signal")
    @mock.patch("oslo_config.cfg.CONF.log_opt_values")
    @mock.patch("oslo_service.systemd.notify_once")
    @mock.patch("oslo_config.cfg.CONF.reload_config_files")
    @mock.patch("oslo_service.service._is_sighup_and_daemon")
    def test_parent_process_reload_config(self,
                                          is_sighup_and_daemon_mock,
                                          reload_config_files_mock,
                                          notify_once_mock,
                                          log_opt_values_mock,
                                          handle_signal_mock,
                                          respawn_children_mock,
                                          stop_mock,
                                          kill_mock,
                                          alarm_mock):
        is_sighup_and_daemon_mock.return_value = True
        respawn_children_mock.side_effect = [None,
                                             eventlet.greenlet.GreenletExit()]
        launcher = service.ProcessLauncher(self.conf)
        launcher.sigcaught = 1
        launcher.children = {}

        wrap_mock = mock.Mock()
        launcher.children[222] = wrap_mock
        launcher.wait()

        reload_config_files_mock.assert_called_once_with()
        wrap_mock.service.reset.assert_called_once_with()

    @mock.patch("oslo_service.service.ProcessLauncher._start_child")
    @mock.patch("oslo_service.service.ProcessLauncher.handle_signal")
    @mock.patch("eventlet.greenio.GreenPipe")
    @mock.patch("os.pipe")
    def test_check_service_base(self, pipe_mock, green_pipe_mock,
                                handle_signal_mock, start_child_mock):
        pipe_mock.return_value = [None, None]
        launcher = service.ProcessLauncher(self.conf)
        serv = _Service()
        launcher.launch_service(serv, workers=0)

    @mock.patch("oslo_service.service.ProcessLauncher._start_child")
    @mock.patch("oslo_service.service.ProcessLauncher.handle_signal")
    @mock.patch("eventlet.greenio.GreenPipe")
    @mock.patch("os.pipe")
    def test_check_service_base_fails(self, pipe_mock, green_pipe_mock,
                                      handle_signal_mock, start_child_mock):
        pipe_mock.return_value = [None, None]
        launcher = service.ProcessLauncher(self.conf)

        class FooService(object):
            def __init__(self):
                pass
        serv = FooService()
        self.assertRaises(TypeError, launcher.launch_service, serv, 0)

    @mock.patch("oslo_service.service.ProcessLauncher._start_child")
    @mock.patch("oslo_service.service.ProcessLauncher.handle_signal")
    @mock.patch("eventlet.greenio.GreenPipe")
    @mock.patch("os.pipe")
    def test_double_sighup(self, pipe_mock, green_pipe_mock,
                           handle_signal_mock, start_child_mock):
        # Test that issuing two SIGHUPs in a row does not exit; then send a
        # TERM that does cause an exit.
        pipe_mock.return_value = [None, None]
        launcher = service.ProcessLauncher(self.conf)
        serv = _Service()
        launcher.launch_service(serv, workers=0)

        def stager():
            # -1: start state
            # 0: post-init
            # 1: first HUP sent
            # 2: second HUP sent
            # 3: TERM sent
            stager.stage += 1
            if stager.stage < 3:
                launcher._handle_hup(1, mock.sentinel.frame)
            elif stager.stage == 3:
                launcher._handle_term(15, mock.sentinel.frame)
            else:
                self.fail("TERM did not kill launcher")
        stager.stage = -1
        handle_signal_mock.side_effect = stager

        launcher.wait()
        self.assertEqual(3, stager.stage)


class GracefulShutdownTestService(service.Service):
    def __init__(self):
        super(GracefulShutdownTestService, self).__init__()
        self.finished_task = event.Event()

    def start(self, sleep_amount):
        def sleep_and_send(finish_event):
            time.sleep(sleep_amount)
            finish_event.send()
        self.tg.add_thread(sleep_and_send, self.finished_task)


def exercise_graceful_test_service(sleep_amount, time_to_wait, graceful):
    svc = GracefulShutdownTestService()
    svc.start(sleep_amount)
    svc.stop(graceful)

    def wait_for_task(svc):
        svc.finished_task.wait()

    return eventlet.timeout.with_timeout(time_to_wait, wait_for_task,
                                         svc=svc, timeout_value="Timeout!")


class ServiceTest(test_base.BaseTestCase):
    def test_graceful_stop(self):
        # Here we wait long enough for the task to gracefully finish.
        self.assertIsNone(exercise_graceful_test_service(1, 2, True))

    def test_ungraceful_stop(self):
        # Here we stop ungracefully, and will never see the task finish.
        self.assertEqual("Timeout!",
                         exercise_graceful_test_service(1, 2, False))


class EventletServerProcessLauncherTest(base.ServiceBaseTestCase):
    def setUp(self):
        super(EventletServerProcessLauncherTest, self).setUp()
        self.conf(args=[], default_config_files=[])
        self.addCleanup(self.conf.reset)
        self.workers = 3

    def run_server(self):
        queue = multiprocessing.Queue()
        # NOTE(bnemec): process_time of 5 needs to be longer than the graceful
        # shutdown timeout in the "exceeded" test below, but also needs to be
        # shorter than the timeout in the regular graceful shutdown test.
        proc = multiprocessing.Process(target=eventlet_service.run,
                                       args=(queue,),
                                       kwargs={'workers': self.workers,
                                               'process_time': 5})
        proc.start()

        port = queue.get()
        conn = socket.create_connection(('127.0.0.1', port))
        # Send request to make the connection active.
        conn.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')

        # NOTE(blk-u): The sleep shouldn't be necessary. There must be a bug in
        # the server implementation where it takes some time to set up the
        # server or signal handlers.
        time.sleep(1)

        return (proc, conn)

    def test_shuts_down_on_sigint_when_client_connected(self):
        proc, conn = self.run_server()

        # check that server is live
        self.assertTrue(proc.is_alive())

        # send SIGINT to the server and wait for it to exit while client still
        # connected.
        os.kill(proc.pid, signal.SIGINT)
        proc.join()
        conn.close()

    def test_graceful_shuts_down_on_sigterm_when_client_connected(self):
        self.config(graceful_shutdown_timeout=7)
        proc, conn = self.run_server()

        # send SIGTERM to the server and wait for it to exit while client still
        # connected.
        os.kill(proc.pid, signal.SIGTERM)

        # server with graceful shutdown must wait forever if
        # option graceful_shutdown_timeout is not specified.
        # we can not wait forever ... so 1 second is enough.
        # NOTE(bnemec): In newer versions of eventlet that drop idle
        # connections, this needs to be long enough to allow the signal
        # handler to fire but short enough that our request doesn't complete
        # or the connection will be closed and the server will stop.
        time.sleep(1)

        self.assertTrue(proc.is_alive())

        conn.close()
        proc.join()

    def test_graceful_stop_with_exceeded_graceful_shutdown_timeout(self):
        # Server must exit if graceful_shutdown_timeout exceeded
        graceful_shutdown_timeout = 4
        self.config(graceful_shutdown_timeout=graceful_shutdown_timeout)
        proc, conn = self.run_server()

        time_before = time.time()
        os.kill(proc.pid, signal.SIGTERM)
        self.assertTrue(proc.is_alive())
        proc.join()
        self.assertFalse(proc.is_alive())
        time_after = time.time()

        self.assertTrue(time_after - time_before > graceful_shutdown_timeout)


class EventletServerServiceLauncherTest(EventletServerProcessLauncherTest):
    def setUp(self):
        super(EventletServerServiceLauncherTest, self).setUp()
        self.workers = 1
