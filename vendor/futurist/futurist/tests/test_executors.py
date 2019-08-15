# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import threading
import time

from eventlet.green import threading as green_threading
import testscenarios
from testtools import testcase

import futurist
from futurist import rejection
from futurist.tests import base


# Module level functions need to be used since the process pool
# executor can not access instance or lambda level functions (since those
# are not pickleable).

def returns_one():
    return 1


def blows_up():
    raise RuntimeError("no worky")


def delayed(wait_secs):
    time.sleep(wait_secs)


class TestExecutors(testscenarios.TestWithScenarios, base.TestCase):
    scenarios = [
        ('sync', {'executor_cls': futurist.SynchronousExecutor,
                  'restartable': True, 'executor_kwargs': {}}),
        ('green_sync', {'executor_cls': futurist.SynchronousExecutor,
                        'restartable': True,
                        'executor_kwargs': {'green': True}}),
        ('green', {'executor_cls': futurist.GreenThreadPoolExecutor,
                   'restartable': False, 'executor_kwargs': {}}),
        ('thread', {'executor_cls': futurist.ThreadPoolExecutor,
                    'restartable': False, 'executor_kwargs': {}}),
        ('process', {'executor_cls': futurist.ProcessPoolExecutor,
                     'restartable': False, 'executor_kwargs': {}}),
    ]

    def setUp(self):
        super(TestExecutors, self).setUp()
        self.executor = self.executor_cls(**self.executor_kwargs)

    def tearDown(self):
        super(TestExecutors, self).tearDown()
        self.executor.shutdown()
        self.executor = None

    def test_run_one(self):
        fut = self.executor.submit(returns_one)
        self.assertEqual(1, fut.result())
        self.assertTrue(fut.done())

    def test_blows_up(self):
        fut = self.executor.submit(blows_up)
        self.assertRaises(RuntimeError, fut.result)
        self.assertIsInstance(fut.exception(), RuntimeError)

    def test_gather_stats(self):
        self.executor.submit(blows_up)
        self.executor.submit(delayed, 0.2)
        self.executor.submit(returns_one)
        self.executor.shutdown()

        self.assertEqual(3, self.executor.statistics.executed)
        self.assertEqual(1, self.executor.statistics.failures)
        self.assertGreaterEqual(self.executor.statistics.runtime,
                                # It appears that the thread run loop
                                # may call this before 0.2 seconds (or 0.2
                                # will not be represented as a float correctly)
                                # is really up so accommodate for that
                                # happening...
                                0.199)

    def test_post_shutdown_raises(self):
        executor = self.executor_cls(**self.executor_kwargs)
        executor.shutdown()
        self.assertRaises(RuntimeError, executor.submit, returns_one)

    def test_restartable(self):
        if not self.restartable:
            raise testcase.TestSkipped("not restartable")
        else:
            executor = self.executor_cls(**self.executor_kwargs)
            fut = executor.submit(returns_one)
            self.assertEqual(1, fut.result())
            executor.shutdown()
            self.assertEqual(1, executor.statistics.executed)

            self.assertRaises(RuntimeError, executor.submit, returns_one)

            executor.restart()
            self.assertEqual(0, executor.statistics.executed)
            fut = executor.submit(returns_one)
            self.assertEqual(1, fut.result())
            self.assertEqual(1, executor.statistics.executed)
            executor.shutdown()

    def test_alive(self):
        with self.executor_cls(**self.executor_kwargs) as executor:
            self.assertTrue(executor.alive)
        self.assertFalse(executor.alive)

    def test_done_callback(self):
        happy_completed = []
        unhappy_completed = []

        def on_done(fut):
            if fut.exception():
                unhappy_completed.append(fut)
            else:
                happy_completed.append(fut)

        for i in range(0, 10):
            if i % 2 == 0:
                fut = self.executor.submit(returns_one)
            else:
                fut = self.executor.submit(blows_up)
            fut.add_done_callback(on_done)

        self.executor.shutdown()
        self.assertEqual(10, len(happy_completed) + len(unhappy_completed))
        self.assertEqual(5, len(unhappy_completed))
        self.assertEqual(5, len(happy_completed))


class TestRejection(testscenarios.TestWithScenarios, base.TestCase):
    rejector = rejection.reject_when_reached(1)

    scenarios = [
        ('green', {'executor_cls': futurist.GreenThreadPoolExecutor,
                   'executor_kwargs': {'check_and_reject': rejector,
                                       'max_workers': 1},
                   'event_cls': green_threading.Event}),
        ('thread', {'executor_cls': futurist.ThreadPoolExecutor,
                    'executor_kwargs': {'check_and_reject': rejector,
                                        'max_workers': 1},
                    'event_cls': threading.Event}),
    ]

    def setUp(self):
        super(TestRejection, self).setUp()
        self.executor = self.executor_cls(**self.executor_kwargs)
        self.addCleanup(self.executor.shutdown, wait=True)

    def test_rejection(self):
        ev = self.event_cls()
        ev_thread_started = self.event_cls()
        self.addCleanup(ev.set)

        def wait_until_set(check_delay):
            ev_thread_started.set()
            while not ev.is_set():
                ev.wait(check_delay)

        # 1 worker + 1 item of backlog
        self.executor.submit(wait_until_set, 0.1)
        # ensure the above thread has started before doing anything
        # else.
        ev_thread_started.wait()
        self.executor.submit(wait_until_set, 0.1)

        self.assertRaises(futurist.RejectedSubmission,
                          self.executor.submit, returns_one)
