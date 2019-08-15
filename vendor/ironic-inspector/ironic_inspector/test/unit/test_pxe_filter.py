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

from automaton import exceptions as automaton_errors
from eventlet import semaphore
import fixtures
from futurist import periodics
import mock
from oslo_config import cfg
import six
import stevedore

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector.pxe_filter import base as pxe_filter
from ironic_inspector.pxe_filter import interface
from ironic_inspector.test import base as test_base

CONF = cfg.CONF


class TestDriverManager(test_base.BaseTest):
    def setUp(self):
        super(TestDriverManager, self).setUp()
        pxe_filter._DRIVER_MANAGER = None
        stevedore_driver_fixture = self.useFixture(fixtures.MockPatchObject(
            stevedore.driver, 'DriverManager', autospec=True))
        self.stevedore_driver_mock = stevedore_driver_fixture.mock

    def test_default(self):
        driver_manager = pxe_filter._driver_manager()
        self.stevedore_driver_mock.assert_called_once_with(
            pxe_filter._STEVEDORE_DRIVER_NAMESPACE,
            name='iptables',
            invoke_on_load=True
        )
        self.assertIsNotNone(driver_manager)
        self.assertIs(pxe_filter._DRIVER_MANAGER, driver_manager)

    def test_pxe_filter_name(self):
        CONF.set_override('driver', 'foo', 'pxe_filter')
        driver_manager = pxe_filter._driver_manager()
        self.stevedore_driver_mock.assert_called_once_with(
            pxe_filter._STEVEDORE_DRIVER_NAMESPACE,
            'foo',
            invoke_on_load=True
        )
        self.assertIsNotNone(driver_manager)
        self.assertIs(pxe_filter._DRIVER_MANAGER, driver_manager)

    def test_default_existing_driver_manager(self):
        pxe_filter._DRIVER_MANAGER = True
        driver_manager = pxe_filter._driver_manager()
        self.stevedore_driver_mock.assert_not_called()
        self.assertIs(pxe_filter._DRIVER_MANAGER, driver_manager)


class TestDriverManagerLoading(test_base.BaseTest):
    def setUp(self):
        super(TestDriverManagerLoading, self).setUp()
        pxe_filter._DRIVER_MANAGER = None

    @mock.patch.object(pxe_filter, 'NoopFilter', autospec=True)
    def test_pxe_filter_driver_loads(self, noop_driver_cls):
        CONF.set_override('driver', 'noop', 'pxe_filter')
        driver_manager = pxe_filter._driver_manager()
        noop_driver_cls.assert_called_once_with()
        self.assertIs(noop_driver_cls.return_value, driver_manager.driver)

    def test_invalid_filter_driver(self):
        CONF.set_override('driver', 'foo', 'pxe_filter')
        six.assertRaisesRegex(self, stevedore.exception.NoMatches, 'foo',
                              pxe_filter._driver_manager)
        self.assertIsNone(pxe_filter._DRIVER_MANAGER)


class BaseFilterBaseTest(test_base.BaseTest):
    def setUp(self):
        super(BaseFilterBaseTest, self).setUp()
        self.mock_lock = mock.MagicMock(spec=semaphore.BoundedSemaphore)
        self.mock_bounded_semaphore = self.useFixture(
            fixtures.MockPatchObject(semaphore, 'BoundedSemaphore')).mock
        self.mock_bounded_semaphore.return_value = self.mock_lock
        self.driver = pxe_filter.NoopFilter()

    def assert_driver_is_locked(self):
        """Assert the driver is currently locked and wasn't locked before."""
        self.driver.lock.__enter__.assert_called_once_with()
        self.driver.lock.__exit__.assert_not_called()

    def assert_driver_was_locked_once(self):
        """Assert the driver was locked exactly once before."""
        self.driver.lock.__enter__.assert_called_once_with()
        self.driver.lock.__exit__.assert_called_once_with(None, None, None)

    def assert_driver_was_not_locked(self):
        """Assert the driver was not locked"""
        self.mock_lock.__enter__.assert_not_called()
        self.mock_lock.__exit__.assert_not_called()


class TestLockedDriverEvent(BaseFilterBaseTest):
    def setUp(self):
        super(TestLockedDriverEvent, self).setUp()
        self.mock_fsm_reset_on_error = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'fsm_reset_on_error')).mock
        self.expected_args = (None,)
        self.expected_kwargs = {'foo': None}
        self.mock_fsm = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'fsm')).mock
        (self.driver.fsm_reset_on_error.return_value.
            __enter__.return_value) = self.mock_fsm

    def test_locked_driver_event(self):
        event = 'foo'

        @pxe_filter.locked_driver_event(event)
        def fun(driver, *args, **kwargs):
            self.assertIs(self.driver, driver)
            self.assertEqual(self.expected_args, args)
            self.assertEqual(self.expected_kwargs, kwargs)
            self.assert_driver_is_locked()

        self.assert_driver_was_not_locked()
        fun(self.driver, *self.expected_args, **self.expected_kwargs)

        self.mock_fsm_reset_on_error.assert_called_once_with()
        self.mock_fsm.process_event.assert_called_once_with(event)
        self.assert_driver_was_locked_once()


class TestBaseFilterFsmPrecautions(BaseFilterBaseTest):
    def setUp(self):
        super(TestBaseFilterFsmPrecautions, self).setUp()
        self.mock_fsm = self.useFixture(
            fixtures.MockPatchObject(pxe_filter.NoopFilter, 'fsm')).mock
        # NOTE(milan): overriding driver so that the patch ^ is applied
        self.mock_bounded_semaphore.reset_mock()
        self.driver = pxe_filter.NoopFilter()
        self.mock_reset = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'reset')).mock

    def test___init__(self):
        self.assertIs(self.mock_lock, self.driver.lock)
        self.mock_bounded_semaphore.assert_called_once_with()
        self.assertIs(self.mock_fsm, self.driver.fsm)
        self.mock_fsm.initialize.assert_called_once_with(
            start_state=pxe_filter.States.uninitialized)

    def test_fsm_reset_on_error(self):
        with self.driver.fsm_reset_on_error() as fsm:
            self.assertIs(self.mock_fsm, fsm)

        self.mock_reset.assert_not_called()

    def test_fsm_automaton_error(self):

        def fun():
            with self.driver.fsm_reset_on_error():
                raise automaton_errors.NotFound('Oops!')

        self.assertRaisesRegex(pxe_filter.InvalidFilterDriverState,
                               '.*NoopFilter.*Oops!', fun)
        self.mock_reset.assert_not_called()

    def test_fsm_reset_on_error_ctx_custom_error(self):

        class MyError(Exception):
            pass

        def fun():
            with self.driver.fsm_reset_on_error():
                raise MyError('Oops!')

        self.assertRaisesRegex(MyError, 'Oops!', fun)
        self.mock_reset.assert_called_once_with()


class TestBaseFilterInterface(BaseFilterBaseTest):
    def setUp(self):
        super(TestBaseFilterInterface, self).setUp()
        self.mock_get_client = self.useFixture(
            fixtures.MockPatchObject(ir_utils, 'get_client')).mock
        self.mock_ironic = mock.Mock()
        self.mock_get_client.return_value = self.mock_ironic
        self.mock_periodic = self.useFixture(
            fixtures.MockPatchObject(periodics, 'periodic')).mock
        self.mock_reset = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'reset')).mock
        self.mock_log = self.useFixture(
            fixtures.MockPatchObject(pxe_filter, 'LOG')).mock
        self.driver.fsm_reset_on_error = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'fsm_reset_on_error')).mock

    def test_init_filter(self):
        self.driver.init_filter()

        self.mock_log.debug.assert_called_once_with(
            'Initializing the PXE filter driver %s', self.driver)
        self.mock_reset.assert_not_called()

    def test_sync(self):
        self.driver.sync(self.mock_ironic)

        self.mock_reset.assert_not_called()

    def test_tear_down_filter(self):
        self.assert_driver_was_not_locked()
        self.driver.tear_down_filter()

        self.assert_driver_was_locked_once()
        self.mock_reset.assert_called_once_with()

    def test_get_periodic_sync_task(self):
        sync_mock = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'sync')).mock
        self.driver.get_periodic_sync_task()
        self.mock_periodic.assert_called_once_with(spacing=15, enabled=True)
        self.mock_periodic.return_value.call_args[0][0]()
        sync_mock.assert_called_once_with(self.mock_get_client.return_value)

    def test_get_periodic_sync_task_invalid_state(self):
        sync_mock = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'sync')).mock
        sync_mock.side_effect = pxe_filter.InvalidFilterDriverState('Oops!')

        self.driver.get_periodic_sync_task()
        self.mock_periodic.assert_called_once_with(spacing=15, enabled=True)
        self.assertRaisesRegex(periodics.NeverAgain, 'Oops!',
                               self.mock_periodic.return_value.call_args[0][0])

    def test_get_periodic_sync_task_custom_error(self):
        class MyError(Exception):
            pass

        sync_mock = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'sync')).mock
        sync_mock.side_effect = MyError('Oops!')

        self.driver.get_periodic_sync_task()
        self.mock_periodic.assert_called_once_with(spacing=15, enabled=True)
        self.assertRaisesRegex(
            MyError, 'Oops!', self.mock_periodic.return_value.call_args[0][0])

    def test_get_periodic_sync_task_disabled(self):
        CONF.set_override('sync_period', 0, 'pxe_filter')
        self.driver.get_periodic_sync_task()
        self.mock_periodic.assert_called_once_with(spacing=float('inf'),
                                                   enabled=False)

    def test_get_periodic_sync_task_custom_spacing(self):
        CONF.set_override('sync_period', 4224, 'pxe_filter')
        self.driver.get_periodic_sync_task()
        self.mock_periodic.assert_called_once_with(spacing=4224, enabled=True)


class TestDriverReset(BaseFilterBaseTest):
    def setUp(self):
        super(TestDriverReset, self).setUp()
        self.mock_fsm = self.useFixture(
            fixtures.MockPatchObject(self.driver, 'fsm')).mock

    def test_reset(self):
        self.driver.reset()

        self.assert_driver_was_not_locked()
        self.mock_fsm.process_event.assert_called_once_with(
            pxe_filter.Events.reset)


class TestDriver(test_base.BaseTest):
    def setUp(self):
        super(TestDriver, self).setUp()
        self.mock_driver = mock.Mock(spec=interface.FilterDriver)
        self.mock__driver_manager = self.useFixture(
            fixtures.MockPatchObject(pxe_filter, '_driver_manager')).mock
        self.mock__driver_manager.return_value.driver = self.mock_driver

    def test_driver(self):
        ret = pxe_filter.driver()

        self.assertIs(self.mock_driver, ret)
        self.mock__driver_manager.assert_called_once_with()
