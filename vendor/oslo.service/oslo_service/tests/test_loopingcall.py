# Copyright 2012 Red Hat, Inc.
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

import eventlet
from eventlet.green import threading as greenthreading
import mock
from oslotest import base as test_base

import oslo_service
from oslo_service import fixture
from oslo_service import loopingcall


class LoopingCallTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(LoopingCallTestCase, self).setUp()
        self.num_runs = 0

    def test_return_true(self):
        def _raise_it():
            raise loopingcall.LoopingCallDone(True)

        timer = loopingcall.FixedIntervalLoopingCall(_raise_it)
        self.assertTrue(timer.start(interval=0.5).wait())

    def test_monotonic_timer(self):
        def _raise_it():
            clock = eventlet.hubs.get_hub().clock
            ok = (clock == oslo_service._monotonic)
            raise loopingcall.LoopingCallDone(ok)

        timer = loopingcall.FixedIntervalLoopingCall(_raise_it)
        self.assertTrue(timer.start(interval=0.5).wait())

    def test_eventlet_clock(self):
        # Make sure that by default the oslo_service.service_hub() kicks in,
        # test in the main thread
        hub = eventlet.hubs.get_hub()
        self.assertEqual(oslo_service._monotonic,
                         hub.clock)

    def test_return_false(self):
        def _raise_it():
            raise loopingcall.LoopingCallDone(False)

        timer = loopingcall.FixedIntervalLoopingCall(_raise_it)
        self.assertFalse(timer.start(interval=0.5).wait())

    def test_terminate_on_exception(self):
        def _raise_it():
            raise RuntimeError()

        timer = loopingcall.FixedIntervalLoopingCall(_raise_it)
        self.assertRaises(RuntimeError, timer.start(interval=0.5).wait)

    def _raise_and_then_done(self):
        if self.num_runs == 0:
            raise loopingcall.LoopingCallDone(False)
        else:
            self.num_runs = self.num_runs - 1
            raise RuntimeError()

    def test_do_not_stop_on_exception(self):
        self.useFixture(fixture.SleepFixture())
        self.num_runs = 2

        timer = loopingcall.FixedIntervalLoopingCall(self._raise_and_then_done)
        res = timer.start(interval=0.5, stop_on_exception=False).wait()
        self.assertFalse(res)

    def _wait_for_zero(self):
        """Called at an interval until num_runs == 0."""
        if self.num_runs == 0:
            raise loopingcall.LoopingCallDone(False)
        else:
            self.num_runs = self.num_runs - 1

    def test_no_double_start(self):
        wait_ev = greenthreading.Event()

        def _run_forever_until_set():
            if wait_ev.is_set():
                raise loopingcall.LoopingCallDone(True)

        timer = loopingcall.FixedIntervalLoopingCall(_run_forever_until_set)
        timer.start(interval=0.01)

        self.assertRaises(RuntimeError, timer.start, interval=0.01)

        wait_ev.set()
        timer.wait()

    def test_no_double_stop(self):
        def _raise_it():
            raise loopingcall.LoopingCallDone(False)

        timer = loopingcall.FixedIntervalLoopingCall(_raise_it)
        timer.start(interval=0.5)

        timer.stop()
        timer.stop()

    def test_repeat(self):
        self.useFixture(fixture.SleepFixture())
        self.num_runs = 2

        timer = loopingcall.FixedIntervalLoopingCall(self._wait_for_zero)
        self.assertFalse(timer.start(interval=0.5).wait())

    def assertAlmostEqual(self, expected, actual, precision=7, message=None):
        self.assertEqual(0, round(actual - expected, precision), message)

    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    @mock.patch('oslo_service.loopingcall.LoopingCallBase._elapsed')
    def test_interval_adjustment(self, elapsed_mock, sleep_mock):
        """Ensure the interval is adjusted to account for task duration."""
        self.num_runs = 3

        second = 1
        smidgen = 0.01

        elapsed_mock.side_effect = [second - smidgen,
                                    second + second,
                                    second + smidgen,
                                    ]
        timer = loopingcall.FixedIntervalLoopingCall(self._wait_for_zero)
        timer.start(interval=1.01).wait()

        expected_calls = [0.02, 0.00, 0.00]
        for i, call in enumerate(sleep_mock.call_args_list):
            expected = expected_calls[i]
            args, kwargs = call
            actual = args[0]
            message = ('Call #%d, expected: %s, actual: %s' %
                       (i, expected, actual))
            self.assertAlmostEqual(expected, actual, message=message)

    def test_looping_call_timed_out(self):

        def _fake_task():
            pass

        timer = loopingcall.FixedIntervalWithTimeoutLoopingCall(_fake_task)
        self.assertRaises(loopingcall.LoopingCallTimeOut,
                          timer.start(interval=0.1, timeout=0.3).wait)


class DynamicLoopingCallTestCase(test_base.BaseTestCase):
    def setUp(self):
        super(DynamicLoopingCallTestCase, self).setUp()
        self.num_runs = 0

    def test_return_true(self):
        def _raise_it():
            raise loopingcall.LoopingCallDone(True)

        timer = loopingcall.DynamicLoopingCall(_raise_it)
        self.assertTrue(timer.start().wait())

    def test_monotonic_timer(self):
        def _raise_it():
            clock = eventlet.hubs.get_hub().clock
            ok = (clock == oslo_service._monotonic)
            raise loopingcall.LoopingCallDone(ok)

        timer = loopingcall.DynamicLoopingCall(_raise_it)
        self.assertTrue(timer.start().wait())

    def test_no_double_start(self):
        wait_ev = greenthreading.Event()

        def _run_forever_until_set():
            if wait_ev.is_set():
                raise loopingcall.LoopingCallDone(True)
            else:
                return 0.01

        timer = loopingcall.DynamicLoopingCall(_run_forever_until_set)
        timer.start()

        self.assertRaises(RuntimeError, timer.start)

        wait_ev.set()
        timer.wait()

    def test_return_false(self):
        def _raise_it():
            raise loopingcall.LoopingCallDone(False)

        timer = loopingcall.DynamicLoopingCall(_raise_it)
        self.assertFalse(timer.start().wait())

    def test_terminate_on_exception(self):
        def _raise_it():
            raise RuntimeError()

        timer = loopingcall.DynamicLoopingCall(_raise_it)
        self.assertRaises(RuntimeError, timer.start().wait)

    def _raise_and_then_done(self):
        if self.num_runs == 0:
            raise loopingcall.LoopingCallDone(False)
        else:
            self.num_runs = self.num_runs - 1
            raise RuntimeError()

    def test_do_not_stop_on_exception(self):
        self.useFixture(fixture.SleepFixture())
        self.num_runs = 2

        timer = loopingcall.DynamicLoopingCall(self._raise_and_then_done)
        timer.start(stop_on_exception=False).wait()

    def _wait_for_zero(self):
        """Called at an interval until num_runs == 0."""
        if self.num_runs == 0:
            raise loopingcall.LoopingCallDone(False)
        else:
            self.num_runs = self.num_runs - 1
            sleep_for = self.num_runs * 10 + 1  # dynamic duration
            return sleep_for

    def test_repeat(self):
        self.useFixture(fixture.SleepFixture())
        self.num_runs = 2

        timer = loopingcall.DynamicLoopingCall(self._wait_for_zero)
        self.assertFalse(timer.start().wait())

    def _timeout_task_without_any_return(self):
        pass

    def test_timeout_task_without_return_and_max_periodic(self):
        timer = loopingcall.DynamicLoopingCall(
            self._timeout_task_without_any_return
        )
        self.assertRaises(RuntimeError, timer.start().wait)

    def _timeout_task_without_return_but_with_done(self):
        if self.num_runs == 0:
            raise loopingcall.LoopingCallDone(False)
        else:
            self.num_runs = self.num_runs - 1

    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_timeout_task_without_return(self, sleep_mock):
        self.num_runs = 1
        timer = loopingcall.DynamicLoopingCall(
            self._timeout_task_without_return_but_with_done
        )
        timer.start(periodic_interval_max=5).wait()
        sleep_mock.assert_has_calls([mock.call(5)])

    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_interval_adjustment(self, sleep_mock):
        self.num_runs = 2

        timer = loopingcall.DynamicLoopingCall(self._wait_for_zero)
        timer.start(periodic_interval_max=5).wait()

        sleep_mock.assert_has_calls([mock.call(5), mock.call(1)])

    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_initial_delay(self, sleep_mock):
        self.num_runs = 1

        timer = loopingcall.DynamicLoopingCall(self._wait_for_zero)
        timer.start(initial_delay=3).wait()

        sleep_mock.assert_has_calls([mock.call(3), mock.call(1)])


class TestBackOffLoopingCall(test_base.BaseTestCase):
    @mock.patch('random.SystemRandom.gauss')
    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_exponential_backoff(self, sleep_mock, random_mock):
        def false():
            return False

        random_mock.return_value = .8

        self.assertRaises(loopingcall.LoopingCallTimeOut,
                          loopingcall.BackOffLoopingCall(false).start()
                          .wait)

        expected_times = [mock.call(1.6),
                          mock.call(2.4000000000000004),
                          mock.call(3.6),
                          mock.call(5.4),
                          mock.call(8.1),
                          mock.call(12.15),
                          mock.call(18.225),
                          mock.call(27.337500000000002),
                          mock.call(41.00625),
                          mock.call(61.509375000000006),
                          mock.call(92.26406250000001)]
        self.assertEqual(expected_times, sleep_mock.call_args_list)

    @mock.patch('random.SystemRandom.gauss')
    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_exponential_backoff_negative_value(self, sleep_mock, random_mock):
        def false():
            return False

        # random.gauss() can return negative values
        random_mock.return_value = -.8

        self.assertRaises(loopingcall.LoopingCallTimeOut,
                          loopingcall.BackOffLoopingCall(false).start()
                          .wait)

        expected_times = [mock.call(1.6),
                          mock.call(2.4000000000000004),
                          mock.call(3.6),
                          mock.call(5.4),
                          mock.call(8.1),
                          mock.call(12.15),
                          mock.call(18.225),
                          mock.call(27.337500000000002),
                          mock.call(41.00625),
                          mock.call(61.509375000000006),
                          mock.call(92.26406250000001)]
        self.assertEqual(expected_times, sleep_mock.call_args_list)

    @mock.patch('random.SystemRandom.gauss')
    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_no_backoff(self, sleep_mock, random_mock):
        random_mock.return_value = 1
        func = mock.Mock()
        # func.side_effect
        func.side_effect = [True, True, True, loopingcall.LoopingCallDone(
            retvalue='return value')]

        retvalue = loopingcall.BackOffLoopingCall(func).start().wait()

        expected_times = [mock.call(1), mock.call(1), mock.call(1)]
        self.assertEqual(expected_times, sleep_mock.call_args_list)
        self.assertTrue(retvalue, 'return value')

    @mock.patch('random.SystemRandom.gauss')
    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_no_sleep(self, sleep_mock, random_mock):
        # Any call that executes properly the first time shouldn't sleep
        random_mock.return_value = 1
        func = mock.Mock()
        # func.side_effect
        func.side_effect = loopingcall.LoopingCallDone(retvalue='return value')

        retvalue = loopingcall.BackOffLoopingCall(func).start().wait()
        self.assertFalse(sleep_mock.called)
        self.assertTrue(retvalue, 'return value')

    @mock.patch('random.SystemRandom.gauss')
    @mock.patch('oslo_service.loopingcall.LoopingCallBase._sleep')
    def test_max_interval(self, sleep_mock, random_mock):
        def false():
            return False

        random_mock.return_value = .8

        self.assertRaises(loopingcall.LoopingCallTimeOut,
                          loopingcall.BackOffLoopingCall(false).start(
                              max_interval=60)
                          .wait)

        expected_times = [mock.call(1.6),
                          mock.call(2.4000000000000004),
                          mock.call(3.6),
                          mock.call(5.4),
                          mock.call(8.1),
                          mock.call(12.15),
                          mock.call(18.225),
                          mock.call(27.337500000000002),
                          mock.call(41.00625),
                          mock.call(60),
                          mock.call(60),
                          mock.call(60)]
        self.assertEqual(expected_times, sleep_mock.call_args_list)


class AnException(Exception):
    pass


class UnknownException(Exception):
    pass


class RetryDecoratorTest(test_base.BaseTestCase):
    """Tests for retry decorator class."""

    def test_retry(self):
        result = "RESULT"

        @loopingcall.RetryDecorator()
        def func(*args, **kwargs):
            return result

        self.assertEqual(result, func())

        def func2(*args, **kwargs):
            return result

        retry = loopingcall.RetryDecorator()
        self.assertEqual(result, retry(func2)())
        self.assertTrue(retry._retry_count == 0)

    def test_retry_with_expected_exceptions(self):
        result = "RESULT"
        responses = [AnException(None),
                     AnException(None),
                     result]

        def func(*args, **kwargs):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        sleep_time_incr = 0.01
        retry_count = 2
        retry = loopingcall.RetryDecorator(10, sleep_time_incr, 10,
                                           (AnException,))
        self.assertEqual(result, retry(func)())
        self.assertTrue(retry._retry_count == retry_count)
        self.assertEqual(retry_count * sleep_time_incr, retry._sleep_time)

    def test_retry_with_max_retries(self):
        responses = [AnException(None),
                     AnException(None),
                     AnException(None)]

        def func(*args, **kwargs):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        retry = loopingcall.RetryDecorator(2, 0, 0,
                                           (AnException,))
        self.assertRaises(AnException, retry(func))
        self.assertTrue(retry._retry_count == 2)

    def test_retry_with_unexpected_exception(self):

        def func(*args, **kwargs):
            raise UnknownException(None)

        retry = loopingcall.RetryDecorator()
        self.assertRaises(UnknownException, retry(func))
        self.assertTrue(retry._retry_count == 0)
