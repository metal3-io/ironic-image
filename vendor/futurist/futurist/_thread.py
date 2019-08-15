# -*- coding: utf-8 -*-

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

import atexit
import sys
import threading
import weakref

import six
from six.moves import queue as compat_queue


class Threading(object):

    @staticmethod
    def event_object(*args, **kwargs):
        return threading.Event(*args, **kwargs)

    @staticmethod
    def lock_object(*args, **kwargs):
        return threading.Lock(*args, **kwargs)

    @staticmethod
    def rlock_object(*args, **kwargs):
        return threading.RLock(*args, **kwargs)

    @staticmethod
    def condition_object(*args, **kwargs):
        return threading.Condition(*args, **kwargs)


_to_be_cleaned = weakref.WeakKeyDictionary()
_dying = False


if six.PY2:
    # This ensures joining responds to keyboard interrupts.
    join_thread = lambda thread: thread.join(sys.maxint)
else:
    # Not needed on py3 or newer...
    join_thread = lambda thread: thread.join()


_TOMBSTONE = object()


class ThreadWorker(threading.Thread):
    MAX_IDLE_FOR = 1

    def __init__(self, executor, work_queue):
        super(ThreadWorker, self).__init__()
        self.work_queue = work_queue
        self.should_stop = False
        self.idle = False
        self.daemon = True
        # Ensure that when the owning executor gets cleaned up that these
        # threads also get shutdown (if they were not already shutdown).
        self.executor_ref = weakref.ref(
            executor, lambda _obj: work_queue.put(_TOMBSTONE))

    @classmethod
    def create_and_register(cls, executor, work_queue):
        w = cls(executor, work_queue)
        # Ensure that on shutdown, if threads still exist that we get
        # around to cleaning them up and waiting for them to correctly stop.
        #
        # TODO(harlowja): use a weakrefset in the future, as we don't
        # really care about the values...
        _to_be_cleaned[w] = True
        return w

    def _is_dying(self):
        if self.should_stop or _dying:
            return True
        executor = self.executor_ref()
        if executor is None:
            return True
        # Avoid confusing the GC with cycles (since each executor
        # references its known workers)...
        del executor
        return False

    def _wait_for_work(self):
        self.idle = True
        work = None
        while work is None:
            try:
                work = self.work_queue.get(True, self.MAX_IDLE_FOR)
            except compat_queue.Empty:
                if self._is_dying():
                    work = _TOMBSTONE
        self.idle = False
        return work

    def stop(self, soon_as_possible=False):
        if soon_as_possible:
            # This will potentially leave unfinished work on queues.
            self.should_stop = True
        self.work_queue.put(_TOMBSTONE)

    def run(self):
        while not self._is_dying():
            work = self._wait_for_work()
            try:
                if work is _TOMBSTONE:
                    # Ensure any other threads on the same queue also get
                    # the tombstone object...
                    self.work_queue.put(_TOMBSTONE)
                    return
                else:
                    work.run()
            finally:
                # Avoid any potential (self) references to the work item
                # in tracebacks or similar...
                del work


def _clean_up():
    """Ensure all threads that were created were destroyed cleanly."""
    global _dying
    _dying = True
    threads_to_wait_for = []
    while _to_be_cleaned:
        worker, _work_val = _to_be_cleaned.popitem()
        worker.stop(soon_as_possible=True)
        threads_to_wait_for.append(worker)
    while threads_to_wait_for:
        worker = threads_to_wait_for.pop()
        try:
            join_thread(worker)
        finally:
            del worker


atexit.register(_clean_up)
