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

import time

import eventlet
import testscenarios

import futurist
from futurist.tests import base
from futurist import waiters


# Module level functions need to be used since the process pool
# executor can not access instance or lambda level functions (since those
# are not pickleable).

def mini_delay(use_eventlet_sleep=False):
    if use_eventlet_sleep:
        eventlet.sleep(0.1)
    else:
        time.sleep(0.1)
    return 1


class TestWaiters(testscenarios.TestWithScenarios, base.TestCase):
    scenarios = [
        ('sync', {'executor_cls': futurist.SynchronousExecutor,
                  'executor_kwargs': {}, 'use_eventlet_sleep': False}),
        ('green_sync', {'executor_cls': futurist.SynchronousExecutor,
                        'executor_kwargs': {'green': True},
                        'use_eventlet_sleep': True}),
        ('green', {'executor_cls': futurist.GreenThreadPoolExecutor,
                   'executor_kwargs': {}, 'use_eventlet_sleep': True}),
        ('thread', {'executor_cls': futurist.ThreadPoolExecutor,
                    'executor_kwargs': {}, 'use_eventlet_sleep': False}),
        ('process', {'executor_cls': futurist.ProcessPoolExecutor,
                     'executor_kwargs': {}, 'use_eventlet_sleep': False}),
    ]

    def setUp(self):
        super(TestWaiters, self).setUp()
        self.executor = self.executor_cls(**self.executor_kwargs)

    def tearDown(self):
        super(TestWaiters, self).tearDown()
        self.executor.shutdown()
        self.executor = None

    def test_wait_for_any(self):
        fs = []
        for _i in range(0, 10):
            fs.append(self.executor.submit(
                mini_delay, use_eventlet_sleep=self.use_eventlet_sleep))
        all_done_fs = []
        total_fs = len(fs)
        while len(all_done_fs) != total_fs:
            done, not_done = waiters.wait_for_any(fs)
            all_done_fs.extend(done)
            fs = not_done
        self.assertEqual(total_fs, sum(f.result() for f in all_done_fs))

    def test_wait_for_all(self):
        fs = []
        for _i in range(0, 10):
            fs.append(self.executor.submit(
                mini_delay, use_eventlet_sleep=self.use_eventlet_sleep))
        done_fs, not_done_fs = waiters.wait_for_all(fs)
        self.assertEqual(len(fs), sum(f.result() for f in done_fs))
        self.assertEqual(0, len(not_done_fs))

    def test_no_mixed_wait_for_any(self):
        fs = [futurist.GreenFuture(), futurist.Future()]
        self.assertRaises(RuntimeError, waiters.wait_for_any, fs)

    def test_no_mixed_wait_for_all(self):
        fs = [futurist.GreenFuture(), futurist.Future()]
        self.assertRaises(RuntimeError, waiters.wait_for_all, fs)
