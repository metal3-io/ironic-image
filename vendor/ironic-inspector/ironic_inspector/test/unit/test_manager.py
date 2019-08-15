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

import json

import fixtures
from ironic_lib import mdns
import mock
import oslo_messaging as messaging

from ironic_inspector.common import keystone
from ironic_inspector.common import swift
from ironic_inspector.conductor import manager
import ironic_inspector.conf
from ironic_inspector import introspect
from ironic_inspector import process
from ironic_inspector.test import base as test_base
from ironic_inspector import utils

CONF = ironic_inspector.conf.CONF


class BaseManagerTest(test_base.NodeTest):
    def setUp(self):
        super(BaseManagerTest, self).setUp()
        self.mock_log = self.useFixture(fixtures.MockPatchObject(
            manager, 'LOG')).mock
        self.mock__shutting_down = (self.useFixture(fixtures.MockPatchObject(
            manager.semaphore, 'Semaphore', autospec=True))
            .mock.return_value)
        self.mock__shutting_down.acquire.return_value = True
        self.manager = manager.ConductorManager()
        self.context = {}
        self.token = None


class TestManagerInitHost(BaseManagerTest):
    def setUp(self):
        super(TestManagerInitHost, self).setUp()
        self.mock_db_init = self.useFixture(fixtures.MockPatchObject(
            manager.db, 'init')).mock
        self.mock_validate_processing_hooks = self.useFixture(
            fixtures.MockPatchObject(manager.plugins_base,
                                     'validate_processing_hooks')).mock
        self.mock_filter = self.useFixture(fixtures.MockPatchObject(
            manager.pxe_filter, 'driver')).mock.return_value
        self.mock_periodic = self.useFixture(fixtures.MockPatchObject(
            manager.periodics, 'periodic')).mock
        self.mock_PeriodicWorker = self.useFixture(fixtures.MockPatchObject(
            manager.periodics, 'PeriodicWorker')).mock
        self.mock_executor = self.useFixture(fixtures.MockPatchObject(
            manager.utils, 'executor')).mock
        self.mock_ExistingExecutor = self.useFixture(fixtures.MockPatchObject(
            manager.periodics, 'ExistingExecutor')).mock
        self.mock_exit = self.useFixture(fixtures.MockPatchObject(
            manager.sys, 'exit')).mock

    def assert_periodics(self):
        outer_cleanup_decorator_call = mock.call(
            spacing=CONF.clean_up_period)
        self.mock_periodic.assert_has_calls([
            outer_cleanup_decorator_call,
            mock.call()(manager.periodic_clean_up)])

        inner_decorator = self.mock_periodic.return_value
        inner_cleanup_decorator_call = mock.call(
            manager.periodic_clean_up)
        inner_decorator.assert_has_calls([inner_cleanup_decorator_call])

        self.mock_ExistingExecutor.assert_called_once_with(
            self.mock_executor.return_value)

        periodic_worker = self.mock_PeriodicWorker.return_value

        periodic_sync = self.mock_filter.get_periodic_sync_task.return_value
        callables = [(periodic_sync, None, None),
                     (inner_decorator.return_value, None, None)]
        self.mock_PeriodicWorker.assert_called_once_with(
            callables=callables,
            executor_factory=self.mock_ExistingExecutor.return_value,
            on_failure=self.manager._periodics_watchdog)
        self.assertIs(periodic_worker, self.manager._periodics_worker)

        self.mock_executor.return_value.submit.assert_called_once_with(
            self.manager._periodics_worker.start)

    def test_no_introspection_data_store(self):
        CONF.set_override('store_data', 'none', 'processing')
        self.manager.init_host()
        self.mock_log.warning.assert_called_once_with(
            'Introspection data will not be stored. Change "[processing] '
            'store_data" option if this is not the desired behavior')

    @mock.patch.object(mdns, 'Zeroconf', autospec=True)
    def test_init_host(self, mock_zc):
        self.manager.init_host()
        self.mock_db_init.assert_called_once_with()
        self.mock_validate_processing_hooks.assert_called_once_with()
        self.mock_filter.init_filter.assert_called_once_with()
        self.assert_periodics()
        self.assertFalse(mock_zc.called)

    def test_init_host_validate_processing_hooks_exception(self):
        class MyError(Exception):
            pass

        error = MyError('Oops!')
        self.mock_validate_processing_hooks.side_effect = error

        # NOTE(milan): have to stop executing the test case at this point to
        # simulate a real sys.exit() call
        self.mock_exit.side_effect = SystemExit('Stop!')
        self.assertRaisesRegex(SystemExit, 'Stop!', self.manager.init_host)

        self.mock_db_init.assert_called_once_with()
        self.mock_log.critical.assert_called_once_with(str(error))
        self.mock_exit.assert_called_once_with(1)
        self.mock_filter.init_filter.assert_not_called()

    @mock.patch.object(mdns, 'Zeroconf', autospec=True)
    @mock.patch.object(keystone, 'get_endpoint', autospec=True)
    def test_init_host_with_mdns(self, mock_endpoint, mock_zc):
        CONF.set_override('enable_mdns', True)
        self.manager.init_host()
        self.mock_db_init.assert_called_once_with()
        self.mock_validate_processing_hooks.assert_called_once_with()
        self.mock_filter.init_filter.assert_called_once_with()
        self.assert_periodics()
        mock_zc.return_value.register_service.assert_called_once_with(
            'baremetal-introspection', mock_endpoint.return_value)

    @mock.patch.object(utils, 'get_coordinator', autospec=True)
    @mock.patch.object(keystone, 'get_endpoint', autospec=True)
    def test_init_host_with_coordinator(self, mock_endpoint, mock_get_coord):
        CONF.set_override('standalone', False)
        mock_coordinator = mock.MagicMock()
        mock_get_coord.return_value = mock_coordinator
        self.manager.init_host()
        self.mock_db_init.assert_called_once_with()
        self.mock_validate_processing_hooks.assert_called_once_with()
        self.mock_filter.init_filter.assert_called_once_with()
        self.assert_periodics()
        mock_get_coord.assert_called_once_with()
        mock_coordinator.start.assert_called_once_with()

    @mock.patch.object(manager.ConductorManager, 'del_host')
    @mock.patch.object(utils, 'get_coordinator', autospec=True)
    @mock.patch.object(keystone, 'get_endpoint', autospec=True)
    def test_init_host_with_coordinator_failed(self, mock_endpoint,
                                               mock_get_coord, mock_del_host):
        CONF.set_override('standalone', False)
        mock_get_coord.side_effect = (utils.Error('Reaching coordination '
                                                  'backend failed.'),
                                      None)
        self.assertRaises(utils.Error, self.manager.init_host)
        self.mock_db_init.assert_called_once_with()
        self.mock_validate_processing_hooks.assert_called_once_with()
        self.mock_filter.init_filter.assert_called_once_with()
        self.assert_periodics()
        mock_get_coord.assert_called_once_with()
        mock_del_host.assert_called_once_with()


class TestManagerDelHost(BaseManagerTest):
    def setUp(self):
        super(TestManagerDelHost, self).setUp()
        self.mock_filter = self.useFixture(fixtures.MockPatchObject(
            manager.pxe_filter, 'driver')).mock.return_value
        self.mock_executor = mock.Mock()
        self.mock_executor.alive = True
        self.mock_get_executor = self.useFixture(fixtures.MockPatchObject(
            manager.utils, 'executor')).mock
        self.mock_get_executor.return_value = self.mock_executor
        self.mock__periodic_worker = self.useFixture(fixtures.MockPatchObject(
            self.manager, '_periodics_worker')).mock
        self.mock_exit = self.useFixture(fixtures.MockPatchObject(
            manager.sys, 'exit')).mock

    def test_del_host(self):
        self.manager.del_host()

        self.mock__shutting_down.acquire.assert_called_once_with(
            blocking=False)
        self.mock__periodic_worker.stop.assert_called_once_with()
        self.mock__periodic_worker.wait.assert_called_once_with()
        self.assertIsNone(self.manager._periodics_worker)
        self.mock_executor.shutdown.assert_called_once_with(wait=True)
        self.mock_filter.tear_down_filter.assert_called_once_with()
        self.mock__shutting_down.release.assert_called_once_with()

    def test_del_host_with_mdns(self):
        mock_zc = mock.Mock(spec=mdns.Zeroconf)
        self.manager._zeroconf = mock_zc

        self.manager.del_host()

        mock_zc.close.assert_called_once_with()
        self.assertIsNone(self.manager._zeroconf)
        self.mock__shutting_down.acquire.assert_called_once_with(
            blocking=False)
        self.mock__periodic_worker.stop.assert_called_once_with()
        self.mock__periodic_worker.wait.assert_called_once_with()
        self.assertIsNone(self.manager._periodics_worker)
        self.mock_executor.shutdown.assert_called_once_with(wait=True)
        self.mock_filter.tear_down_filter.assert_called_once_with()
        self.mock__shutting_down.release.assert_called_once_with()

    def test_del_host_race(self):
        self.mock__shutting_down.acquire.return_value = False

        self.manager.del_host()

        self.mock__shutting_down.acquire.assert_called_once_with(
            blocking=False)
        self.mock_log.warning.assert_called_once_with(
            'Attempted to shut down while already shutting down')
        self.mock__periodic_worker.stop.assert_not_called()
        self.mock__periodic_worker.wait.assert_not_called()
        self.assertIs(self.mock__periodic_worker,
                      self.manager._periodics_worker)
        self.mock_executor.shutdown.assert_not_called()
        self.mock_filter.tear_down_filter.assert_not_called()
        self.mock__shutting_down.release.assert_not_called()
        self.mock_exit.assert_not_called()

    def test_del_host_worker_exception(self):
        class MyError(Exception):
            pass

        error = MyError('Oops!')
        self.mock__periodic_worker.wait.side_effect = error

        self.manager.del_host()

        self.mock__shutting_down.acquire.assert_called_once_with(
            blocking=False)
        self.mock__periodic_worker.stop.assert_called_once_with()
        self.mock__periodic_worker.wait.assert_called_once_with()
        self.mock_log.exception.assert_called_once_with(
            'Service error occurred when stopping periodic workers. Error: %s',
            error)
        self.assertIsNone(self.manager._periodics_worker)
        self.mock_executor.shutdown.assert_called_once_with(wait=True)
        self.mock_filter.tear_down_filter.assert_called_once_with()
        self.mock__shutting_down.release.assert_called_once_with()

    def test_del_host_no_worker(self):
        self.manager._periodics_worker = None

        self.manager.del_host()

        self.mock__shutting_down.acquire.assert_called_once_with(
            blocking=False)
        self.mock__periodic_worker.stop.assert_not_called()
        self.mock__periodic_worker.wait.assert_not_called()
        self.assertIsNone(self.manager._periodics_worker)
        self.mock_executor.shutdown.assert_called_once_with(wait=True)
        self.mock_filter.tear_down_filter.assert_called_once_with()
        self.mock__shutting_down.release.assert_called_once_with()

    def test_del_host_stopped_executor(self):
        self.mock_executor.alive = False

        self.manager.del_host()

        self.mock__shutting_down.acquire.assert_called_once_with(
            blocking=False)
        self.mock__periodic_worker.stop.assert_called_once_with()
        self.mock__periodic_worker.wait.assert_called_once_with()
        self.assertIsNone(self.manager._periodics_worker)
        self.mock_executor.shutdown.assert_not_called()
        self.mock_filter.tear_down_filter.assert_called_once_with()
        self.mock__shutting_down.release.assert_called_once_with()

    @mock.patch.object(utils, 'get_coordinator', autospec=True)
    def test_del_host_with_coordinator(self, mock_get_coord):
        CONF.set_override('standalone', False)
        mock_coordinator = mock.MagicMock()
        mock_coordinator.is_started = True
        mock_get_coord.return_value = mock_coordinator

        self.manager.del_host()

        self.assertIsNone(self.manager._zeroconf)
        self.mock__shutting_down.acquire.assert_called_once_with(
            blocking=False)
        self.mock__periodic_worker.stop.assert_called_once_with()
        self.mock__periodic_worker.wait.assert_called_once_with()
        self.assertIsNone(self.manager._periodics_worker)
        self.mock_executor.shutdown.assert_called_once_with(wait=True)
        self.mock_filter.tear_down_filter.assert_called_once_with()
        self.mock__shutting_down.release.assert_called_once_with()
        mock_coordinator.stop.called_once_with()


class TestManagerPeriodicWatchDog(BaseManagerTest):
    def setUp(self):
        super(TestManagerPeriodicWatchDog, self).setUp()
        self.mock_get_callable_name = self.useFixture(fixtures.MockPatchObject(
            manager.reflection, 'get_callable_name')).mock
        self.mock_spawn = self.useFixture(fixtures.MockPatchObject(
            manager.eventlet, 'spawn')).mock

    def test__periodics_watchdog(self):
        error = RuntimeError('Oops!')

        self.manager._periodics_watchdog(
            callable_=None, activity=None, spacing=None,
            exc_info=(None, error, None), traceback=None)

        self.mock_get_callable_name.assert_called_once_with(None)
        self.mock_spawn.assert_called_once_with(self.manager.del_host)


class TestManagerIntrospect(BaseManagerTest):
    @mock.patch.object(introspect, 'introspect', autospec=True)
    def test_do_introspect(self, introspect_mock):
        self.manager.do_introspection(self.context, self.uuid, self.token)

        introspect_mock.assert_called_once_with(self.uuid, token=self.token,
                                                manage_boot=True)

    @mock.patch.object(introspect, 'introspect', autospec=True)
    def test_do_introspect_with_manage_boot(self, introspect_mock):
        self.manager.do_introspection(self.context, self.uuid, self.token,
                                      False)

        introspect_mock.assert_called_once_with(self.uuid, token=self.token,
                                                manage_boot=False)

    @mock.patch.object(introspect, 'introspect', autospec=True)
    def test_introspect_failed(self, introspect_mock):
        introspect_mock.side_effect = utils.Error("boom")

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_introspection,
                                self.context, self.uuid, self.token)

        self.assertEqual(utils.Error, exc.exc_info[0])
        introspect_mock.assert_called_once_with(self.uuid, token=None,
                                                manage_boot=True)


class TestManagerAbort(BaseManagerTest):
    @mock.patch.object(introspect, 'abort', autospec=True)
    def test_abort_ok(self, abort_mock):
        self.manager.do_abort(self.context, self.uuid, self.token)

        abort_mock.assert_called_once_with(self.uuid, token=self.token)

    @mock.patch.object(introspect, 'abort', autospec=True)
    def test_abort_node_not_found(self, abort_mock):
        abort_mock.side_effect = utils.Error("Not Found.", code=404)

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_abort,
                                self.context, self.uuid, self.token)

        self.assertEqual(utils.Error, exc.exc_info[0])
        abort_mock.assert_called_once_with(self.uuid, token=None)

    @mock.patch.object(introspect, 'abort', autospec=True)
    def test_abort_failed(self, abort_mock):
        exc = utils.Error("Locked.", code=409)
        abort_mock.side_effect = exc

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_abort,
                                self.context, self.uuid, self.token)

        self.assertEqual(utils.Error, exc.exc_info[0])
        abort_mock.assert_called_once_with(self.uuid, token=None)


@mock.patch.object(process, 'reapply', autospec=True)
class TestManagerReapply(BaseManagerTest):

    def setUp(self):
        super(TestManagerReapply, self).setUp()
        CONF.set_override('store_data', 'swift', 'processing')

    @mock.patch.object(swift, 'store_introspection_data', autospec=True)
    @mock.patch.object(swift, 'get_introspection_data', autospec=True)
    def test_ok(self, swift_get_mock, swift_set_mock, reapply_mock):
        swift_get_mock.return_value = json.dumps(self.data)
        self.manager.do_reapply(self.context, self.uuid)
        reapply_mock.assert_called_once_with(self.uuid, data=self.data)

    @mock.patch.object(swift, 'store_introspection_data', autospec=True)
    @mock.patch.object(swift, 'get_introspection_data', autospec=True)
    def test_node_locked(self, swift_get_mock, swift_set_mock, reapply_mock):
        swift_get_mock.return_value = json.dumps(self.data)
        exc = utils.Error('Locked.', code=409)
        reapply_mock.side_effect = exc

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_reapply,
                                self.context, self.uuid)

        self.assertEqual(utils.Error, exc.exc_info[0])
        self.assertIn('Locked.', str(exc.exc_info[1]))
        self.assertEqual(409, exc.exc_info[1].http_code)
        reapply_mock.assert_called_once_with(self.uuid, data=self.data)

    @mock.patch.object(swift, 'store_introspection_data', autospec=True)
    @mock.patch.object(swift, 'get_introspection_data', autospec=True)
    def test_node_not_found(self, swift_get_mock, swift_set_mock,
                            reapply_mock):
        swift_get_mock.return_value = json.dumps(self.data)
        exc = utils.Error('Not found.', code=404)
        reapply_mock.side_effect = exc

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_reapply,
                                self.context, self.uuid)

        self.assertEqual(utils.Error, exc.exc_info[0])
        self.assertIn('Not found.', str(exc.exc_info[1]))
        self.assertEqual(404, exc.exc_info[1].http_code)
        reapply_mock.assert_called_once_with(self.uuid, data=self.data)

    @mock.patch.object(process, 'get_introspection_data', autospec=True)
    def test_generic_error(self, get_data_mock, reapply_mock):
        get_data_mock.return_value = self.data
        exc = utils.Error('Oops', code=400)
        reapply_mock.side_effect = exc

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_reapply,
                                self.context, self.uuid)

        self.assertEqual(utils.Error, exc.exc_info[0])
        self.assertIn('Oops', str(exc.exc_info[1]))
        self.assertEqual(400, exc.exc_info[1].http_code)
        reapply_mock.assert_called_once_with(self.uuid, data=self.data)
        get_data_mock.assert_called_once_with(self.uuid, processed=False,
                                              get_json=True)

    @mock.patch.object(process, 'get_introspection_data', autospec=True)
    def test_get_introspection_data_error(self, get_data_mock, reapply_mock):
        exc = utils.Error('The store is empty', code=404)
        get_data_mock.side_effect = exc

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_reapply,
                                self.context, self.uuid)

        self.assertEqual(utils.Error, exc.exc_info[0])
        self.assertIn('The store is empty', str(exc.exc_info[1]))
        self.assertEqual(404, exc.exc_info[1].http_code)
        get_data_mock.assert_called_once_with(self.uuid, processed=False,
                                              get_json=True)
        self.assertFalse(reapply_mock.called)

    def test_store_data_disabled(self, reapply_mock):
        CONF.set_override('store_data', 'none', 'processing')

        exc = self.assertRaises(messaging.rpc.ExpectedException,
                                self.manager.do_reapply,
                                self.context, self.uuid)

        self.assertEqual(utils.Error, exc.exc_info[0])
        self.assertIn('Inspector is not configured to store introspection '
                      'data', str(exc.exc_info[1]))
        self.assertEqual(400, exc.exc_info[1].http_code)
        self.assertFalse(reapply_mock.called)

    @mock.patch.object(process, 'get_introspection_data', autospec=True)
    def test_ok_swift(self, get_data_mock, reapply_mock):
        get_data_mock.return_value = self.data
        self.manager.do_reapply(self.context, self.uuid)
        reapply_mock.assert_called_once_with(self.uuid, data=self.data)
        get_data_mock.assert_called_once_with(self.uuid, processed=False,
                                              get_json=True)

    @mock.patch.object(process, 'get_introspection_data', autospec=True)
    def test_ok_db(self, get_data_mock, reapply_mock):
        get_data_mock.return_value = self.data
        CONF.set_override('store_data', 'database', 'processing')
        self.manager.do_reapply(self.context, self.uuid)
        reapply_mock.assert_called_once_with(self.uuid, data=self.data)
        get_data_mock.assert_called_once_with(self.uuid, processed=False,
                                              get_json=True)

    @mock.patch.object(process, 'store_introspection_data', autospec=True)
    @mock.patch.object(process, 'get_introspection_data', autospec=True)
    def test_reapply_with_data(self, get_mock, store_mock, reapply_mock):
        self.manager.do_reapply(self.context, self.uuid, data=self.data)
        reapply_mock.assert_called_once_with(self.uuid, data=self.data)
        store_mock.assert_called_once_with(self.uuid, self.data,
                                           processed=False)
        self.assertFalse(get_mock.called)
