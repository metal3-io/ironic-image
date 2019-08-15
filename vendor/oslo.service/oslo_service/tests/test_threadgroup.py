# Copyright (c) 2012 Rackspace Hosting
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
Unit Tests for thread groups
"""

import time

from eventlet import event

from oslotest import base as test_base

from oslo_service import threadgroup


class ThreadGroupTestCase(test_base.BaseTestCase):
    """Test cases for thread group."""
    def setUp(self):
        super(ThreadGroupTestCase, self).setUp()
        self.tg = threadgroup.ThreadGroup()
        self.addCleanup(self.tg.stop)

    def test_add_dynamic_timer(self):

        def foo(*args, **kwargs):
            pass
        initial_delay = 1
        periodic_interval_max = 2
        self.tg.add_dynamic_timer(foo, initial_delay, periodic_interval_max,
                                  'arg', kwarg='kwarg')

        self.assertEqual(1, len(self.tg.timers))

        timer = self.tg.timers[0]
        self.assertTrue(timer._running)
        self.assertEqual(('arg',), timer.args)
        self.assertEqual({'kwarg': 'kwarg'}, timer.kw)

    def test_add_dynamic_timer_args(self):
        def foo(*args, **kwargs):
            pass

        self.tg.add_dynamic_timer_args(foo, ['arg'], {'kwarg': 'kwarg'},
                                       initial_delay=1,
                                       periodic_interval_max=2,
                                       stop_on_exception=False)

        self.assertEqual(1, len(self.tg.timers))

        timer = self.tg.timers[0]
        self.assertTrue(timer._running)
        self.assertEqual(('arg',), timer.args)
        self.assertEqual({'kwarg': 'kwarg'}, timer.kw)

    def test_add_timer(self):
        def foo(*args, **kwargs):
            pass

        self.tg.add_timer(1, foo, 1,
                          'arg', kwarg='kwarg')

        self.assertEqual(1, len(self.tg.timers))

        timer = self.tg.timers[0]
        self.assertTrue(timer._running)
        self.assertEqual(('arg',), timer.args)
        self.assertEqual({'kwarg': 'kwarg'}, timer.kw)

    def test_add_timer_args(self):
        def foo(*args, **kwargs):
            pass

        self.tg.add_timer_args(1, foo, ['arg'], {'kwarg': 'kwarg'},
                               initial_delay=1, stop_on_exception=False)

        self.assertEqual(1, len(self.tg.timers))

        timer = self.tg.timers[0]
        self.assertTrue(timer._running)
        self.assertEqual(('arg',), timer.args)
        self.assertEqual({'kwarg': 'kwarg'}, timer.kw)

    def test_stop_current_thread(self):

        stop_event = event.Event()
        quit_event = event.Event()

        def stop_self(*args, **kwargs):
            if args[0] == 1:
                time.sleep(1)
                self.tg.stop()
                stop_event.send('stop_event')
            quit_event.wait()

        for i in range(0, 4):
            self.tg.add_thread(stop_self, i, kwargs='kwargs')

        stop_event.wait()
        self.assertEqual(1, len(self.tg.threads))
        quit_event.send('quit_event')

    def test_stop_immediately(self):

        def foo(*args, **kwargs):
            time.sleep(1)
        start_time = time.time()
        self.tg.add_thread(foo, 'arg', kwarg='kwarg')
        time.sleep(0)
        self.tg.stop()
        end_time = time.time()

        self.assertEqual(0, len(self.tg.threads))
        self.assertTrue(end_time - start_time < 1)
        self.assertEqual(0, len(self.tg.timers))

    def test_stop_gracefully(self):

        def foo(*args, **kwargs):
            time.sleep(1)
        start_time = time.time()
        self.tg.add_thread(foo, 'arg', kwarg='kwarg')
        self.tg.stop(True)
        end_time = time.time()

        self.assertEqual(0, len(self.tg.threads))
        self.assertTrue(end_time - start_time >= 1)
        self.assertEqual(0, len(self.tg.timers))

    def test_cancel_early(self):

        def foo(*args, **kwargs):
            time.sleep(1)
        self.tg.add_thread(foo, 'arg', kwarg='kwarg')
        self.tg.cancel()

        self.assertEqual(0, len(self.tg.threads))

    def test_cancel_late(self):

        def foo(*args, **kwargs):
            time.sleep(0.3)
        self.tg.add_thread(foo, 'arg', kwarg='kwarg')
        time.sleep(0)
        self.tg.cancel()

        self.assertEqual(1, len(self.tg.threads))

    def test_cancel_timeout(self):

        def foo(*args, **kwargs):
            time.sleep(0.3)
        self.tg.add_thread(foo, 'arg', kwarg='kwarg')
        time.sleep(0)
        self.tg.cancel(timeout=0.2, wait_time=0.1)

        self.assertEqual(0, len(self.tg.threads))

    def test_stop_timers(self):

        def foo(*args, **kwargs):
            pass
        self.tg.add_timer('1234', foo)
        self.assertEqual(1, len(self.tg.timers))
        self.tg.stop_timers()
        self.assertEqual(0, len(self.tg.timers))

    def test_add_and_remove_timer(self):

        def foo(*args, **kwargs):
            pass

        timer = self.tg.add_timer('1234', foo)
        self.assertEqual(1, len(self.tg.timers))
        timer.stop()
        self.assertEqual(1, len(self.tg.timers))

        self.tg.timer_done(timer)
        self.assertEqual(0, len(self.tg.timers))

    def test_add_and_remove_dynamic_timer(self):

        def foo(*args, **kwargs):
            pass
        initial_delay = 1
        periodic_interval_max = 2
        timer = self.tg.add_dynamic_timer(foo, initial_delay,
                                          periodic_interval_max)

        self.assertEqual(1, len(self.tg.timers))
        self.assertTrue(timer._running)

        timer.stop()
        self.assertEqual(1, len(self.tg.timers))

        self.tg.timer_done(timer)
        self.assertEqual(0, len(self.tg.timers))
