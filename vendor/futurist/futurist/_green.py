# -*- coding: utf-8 -*-

#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
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
import sys

from futurist import _utils

try:
    from eventlet import greenpool
    from eventlet import patcher as greenpatcher
    from eventlet import queue as greenqueue

    from eventlet.green import threading as greenthreading
except ImportError:
    greenpatcher, greenpool, greenqueue, greenthreading = (None, None,
                                                           None, None)


if _utils.EVENTLET_AVAILABLE:
    # Aliases that we use and only expose vs the whole of eventlet...
    Pool = greenpool.GreenPool
    Queue = greenqueue.Queue
    is_monkey_patched = greenpatcher.is_monkey_patched

    class GreenThreading(object):

        @staticmethod
        def event_object(*args, **kwargs):
            return greenthreading.Event(*args, **kwargs)

        @staticmethod
        def lock_object(*args, **kwargs):
            return greenthreading.Lock(*args, **kwargs)

        @staticmethod
        def rlock_object(*args, **kwargs):
            return greenthreading.RLock(*args, **kwargs)

        @staticmethod
        def condition_object(*args, **kwargs):
            return greenthreading.Condition(*args, **kwargs)

    threading = GreenThreading()
else:
    threading = None
    Pool = None
    Queue = None
    is_monkey_patched = lambda mod: False


class GreenWorker(object):
    def __init__(self, work, work_queue):
        self.work = work
        self.work_queue = work_queue

    def __call__(self):
        # Run our main piece of work.
        try:
            self.work.run()
        except SystemExit as e:
            exc_info = sys.exc_info()
            try:
                while True:
                    try:
                        w = self.work_queue.get_nowait()
                    except greenqueue.Empty:
                        break

                    try:
                        w.fail(exc_info)
                    finally:
                        self.work_queue.task_done()
            finally:
                del exc_info
                raise e

        # Consume any delayed work before finishing (this is how we finish
        # work that was to big for the pool size, but needs to be finished
        # no matter).
        while True:
            try:
                w = self.work_queue.get_nowait()
            except greenqueue.Empty:
                break
            else:
                try:
                    w.run()
                finally:
                    self.work_queue.task_done()
