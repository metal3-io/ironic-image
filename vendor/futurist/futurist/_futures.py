# -*- coding: utf-8 -*-

#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
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

import functools
import threading

from concurrent import futures as _futures
from concurrent.futures import process as _process
import six

from six.moves import queue as compat_queue

from futurist import _green
from futurist import _thread
from futurist import _utils


TimeoutError = _futures.TimeoutError
CancelledError = _futures.CancelledError


class RejectedSubmission(Exception):
    """Exception raised when a submitted call is rejected (for some reason)."""


# NOTE(harlowja): Allows for simpler access to this type...
Future = _futures.Future


class _Gatherer(object):
    def __init__(self, submit_func, lock_factory, start_before_submit=False):
        self._submit_func = submit_func
        self._stats_lock = lock_factory()
        self._stats = ExecutorStatistics()
        self._start_before_submit = start_before_submit

    @property
    def statistics(self):
        return self._stats

    def clear(self):
        with self._stats_lock:
            self._stats = ExecutorStatistics()

    def _capture_stats(self, started_at, fut):
        """Capture statistics

        :param started_at: when the activity the future has performed
                           was started at
        :param fut: future object
        """
        # If time somehow goes backwards, make sure we cap it at 0.0 instead
        # of having negative elapsed time...
        elapsed = max(0.0, _utils.now() - started_at)
        with self._stats_lock:
            # Use a new collection and lock so that all mutations are seen as
            # atomic and not overlapping and corrupting with other
            # mutations (the clone ensures that others reading the current
            # values will not see a mutated/corrupted one). Since futures may
            # be completed by different threads we need to be extra careful to
            # gather this data in a way that is thread-safe...
            (failures, executed, runtime, cancelled) = (self._stats.failures,
                                                        self._stats.executed,
                                                        self._stats.runtime,
                                                        self._stats.cancelled)
            if fut.cancelled():
                cancelled += 1
            else:
                executed += 1
                if fut.exception() is not None:
                    failures += 1
                runtime += elapsed
            self._stats = ExecutorStatistics(failures=failures,
                                             executed=executed,
                                             runtime=runtime,
                                             cancelled=cancelled)

    def submit(self, fn, *args, **kwargs):
        """Submit work to be executed and capture statistics."""
        if self._start_before_submit:
            started_at = _utils.now()
        fut = self._submit_func(fn, *args, **kwargs)
        if not self._start_before_submit:
            started_at = _utils.now()
        fut.add_done_callback(functools.partial(self._capture_stats,
                                                started_at))
        return fut


class ThreadPoolExecutor(_futures.Executor):
    """Executor that uses a thread pool to execute calls asynchronously.

    It gathers statistics about the submissions executed for post-analysis...

    See: https://docs.python.org/dev/library/concurrent.futures.html
    """

    threading = _thread.Threading()

    def __init__(self, max_workers=None, check_and_reject=None):
        """Initializes a thread pool executor.

        :param max_workers: maximum number of workers that can be
                            simultaneously active at the same time, further
                            submitted work will be queued up when this limit
                            is reached.
        :type max_workers: int
        :param check_and_reject: a callback function that will be provided
                                 two position arguments, the first argument
                                 will be this executor instance, and the second
                                 will be the number of currently queued work
                                 items in this executors backlog; the callback
                                 should raise a :py:class:`.RejectedSubmission`
                                 exception if it wants to have this submission
                                 rejected.
        :type check_and_reject: callback
        """
        if max_workers is None:
            max_workers = _utils.get_optimal_thread_count()
        if max_workers <= 0:
            raise ValueError("Max workers must be greater than zero")
        self._max_workers = max_workers
        self._work_queue = compat_queue.Queue()
        self._shutdown_lock = threading.RLock()
        self._shutdown = False
        self._workers = []
        self._check_and_reject = check_and_reject or (lambda e, waiting: None)
        self._gatherer = _Gatherer(self._submit, self.threading.lock_object)

    @property
    def statistics(self):
        """:class:`.ExecutorStatistics` about the executors executions."""
        return self._gatherer.statistics

    @property
    def alive(self):
        """Accessor to determine if the executor is alive/active."""
        return not self._shutdown

    def _maybe_spin_up(self):
        """Spin up a worker if needed."""
        # Do more advanced idle checks and/or reaping of very idle
        # threads in the future....
        if (not self._workers or
                len(self._workers) < self._max_workers):
            w = _thread.ThreadWorker.create_and_register(
                self, self._work_queue)
            # Always save it before we start (so that even if we fail
            # starting it we can correctly join on it).
            self._workers.append(w)
            w.start()

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            if not self._shutdown:
                self._shutdown = True
                for w in self._workers:
                    w.stop()
        if wait:
            for w in self._workers:
                _thread.join_thread(w)

    def _submit(self, fn, *args, **kwargs):
        f = Future()
        self._maybe_spin_up()
        self._work_queue.put(_utils.WorkItem(f, fn, args, kwargs))
        return f

    def submit(self, fn, *args, **kwargs):
        """Submit some work to be executed (and gather statistics)."""
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('Can not schedule new futures'
                                   ' after being shutdown')
            self._check_and_reject(self, self._work_queue.qsize())
            return self._gatherer.submit(fn, *args, **kwargs)


class ProcessPoolExecutor(_process.ProcessPoolExecutor):
    """Executor that uses a process pool to execute calls asynchronously.

    It gathers statistics about the submissions executed for post-analysis...

    See: https://docs.python.org/dev/library/concurrent.futures.html
    """

    threading = _thread.Threading()

    def __init__(self, max_workers=None):
        if max_workers is None:
            max_workers = _utils.get_optimal_process_count()
        super(ProcessPoolExecutor, self).__init__(max_workers=max_workers)
        if self._max_workers <= 0:
            raise ValueError("Max workers must be greater than zero")
        self._gatherer = _Gatherer(
            # Since our submit will use this gatherer we have to reference
            # the parent submit, bound to this instance (which is what we
            # really want to use anyway).
            super(ProcessPoolExecutor, self).submit,
            self.threading.lock_object)

    @property
    def alive(self):
        """Accessor to determine if the executor is alive/active."""
        return not self._shutdown_thread

    @property
    def statistics(self):
        """:class:`.ExecutorStatistics` about the executors executions."""
        return self._gatherer.statistics

    def submit(self, fn, *args, **kwargs):
        """Submit some work to be executed (and gather statistics)."""
        return self._gatherer.submit(fn, *args, **kwargs)


class SynchronousExecutor(_futures.Executor):
    """Executor that uses the caller to execute calls synchronously.

    This provides an interface to a caller that looks like an executor but
    will execute the calls inside the caller thread instead of executing it
    in a external process/thread for when this type of functionality is
    useful to provide...

    It gathers statistics about the submissions executed for post-analysis...
    """

    threading = _thread.Threading()

    def __init__(self, green=False, run_work_func=lambda work: work.run()):
        """Synchronous executor constructor.

        :param green: when enabled this forces the usage of greened lock
                      classes and green futures (so that the internals of this
                      object operate correctly under eventlet)
        :type green: bool
        :param run_work_func: callable that takes a single work item and
                              runs it (typically in a blocking manner)
        :param run_work_func: callable
        """
        if green and not _utils.EVENTLET_AVAILABLE:
            raise RuntimeError('Eventlet is needed to use a green'
                               ' synchronous executor')
        if not six.callable(run_work_func):
            raise ValueError("Run work parameter expected to be callable")
        self._run_work_func = run_work_func
        self._shutoff = False
        if green:
            self.threading = _green.threading
            self._future_cls = GreenFuture
        else:
            self._future_cls = Future
        self._run_work_func = run_work_func
        self._gatherer = _Gatherer(self._submit,
                                   self.threading.lock_object,
                                   start_before_submit=True)

    @property
    def alive(self):
        """Accessor to determine if the executor is alive/active."""
        return not self._shutoff

    def shutdown(self, wait=True):
        self._shutoff = True

    def restart(self):
        """Restarts this executor (*iff* previously shutoff/shutdown).

        NOTE(harlowja): clears any previously gathered statistics.
        """
        if self._shutoff:
            self._shutoff = False
            self._gatherer.clear()

    @property
    def statistics(self):
        """:class:`.ExecutorStatistics` about the executors executions."""
        return self._gatherer.statistics

    def submit(self, fn, *args, **kwargs):
        """Submit some work to be executed (and gather statistics)."""
        if self._shutoff:
            raise RuntimeError('Can not schedule new futures'
                               ' after being shutdown')
        return self._gatherer.submit(fn, *args, **kwargs)

    def _submit(self, fn, *args, **kwargs):
        fut = self._future_cls()
        self._run_work_func(_utils.WorkItem(fut, fn, args, kwargs))
        return fut


class GreenFuture(Future):
    __doc__ = Future.__doc__

    def __init__(self):
        super(GreenFuture, self).__init__()
        if not _utils.EVENTLET_AVAILABLE:
            raise RuntimeError('Eventlet is needed to use a green future')
        # NOTE(harlowja): replace the built-in condition with a greenthread
        # compatible one so that when getting the result of this future the
        # functions will correctly yield to eventlet. If this is not done then
        # waiting on the future never actually causes the greenthreads to run
        # and thus you wait for infinity.
        if not _green.is_monkey_patched('thread'):
            self._condition = _green.threading.condition_object()


class GreenThreadPoolExecutor(_futures.Executor):
    """Executor that uses a green thread pool to execute calls asynchronously.

    See: https://docs.python.org/dev/library/concurrent.futures.html
    and http://eventlet.net/doc/modules/greenpool.html for information on
    how this works.

    It gathers statistics about the submissions executed for post-analysis...
    """

    threading = _green.threading

    def __init__(self, max_workers=1000, check_and_reject=None):
        """Initializes a green thread pool executor.

        :param max_workers: maximum number of workers that can be
                            simulatenously active at the same time, further
                            submitted work will be queued up when this limit
                            is reached.
        :type max_workers: int
        :param check_and_reject: a callback function that will be provided
                                 two position arguments, the first argument
                                 will be this executor instance, and the second
                                 will be the number of currently queued work
                                 items in this executors backlog; the callback
                                 should raise a :py:class:`.RejectedSubmission`
                                 exception if it wants to have this submission
                                 rejected.
        :type check_and_reject: callback
        """
        if not _utils.EVENTLET_AVAILABLE:
            raise RuntimeError('Eventlet is needed to use a green executor')
        if max_workers <= 0:
            raise ValueError("Max workers must be greater than zero")
        self._max_workers = max_workers
        self._pool = _green.Pool(self._max_workers)
        self._delayed_work = _green.Queue()
        self._check_and_reject = check_and_reject or (lambda e, waiting: None)
        self._shutdown_lock = self.threading.lock_object()
        self._shutdown = False
        self._gatherer = _Gatherer(self._submit,
                                   self.threading.lock_object)

    @property
    def alive(self):
        """Accessor to determine if the executor is alive/active."""
        return not self._shutdown

    @property
    def statistics(self):
        """:class:`.ExecutorStatistics` about the executors executions."""
        return self._gatherer.statistics

    def submit(self, fn, *args, **kwargs):
        """Submit some work to be executed (and gather statistics).

        :param args: non-keyworded arguments
        :type args: list
        :param kwargs: key-value arguments
        :type kwargs: dictionary
        """
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('Can not schedule new futures'
                                   ' after being shutdown')
            self._check_and_reject(self, self._delayed_work.qsize())
            return self._gatherer.submit(fn, *args, **kwargs)

    def _submit(self, fn, *args, **kwargs):
        f = GreenFuture()
        work = _utils.WorkItem(f, fn, args, kwargs)
        if not self._spin_up(work):
            self._delayed_work.put(work)
        return f

    def _spin_up(self, work):
        """Spin up a greenworker if less than max_workers.

        :param work: work to be given to the greenworker
        :returns: whether a green worker was spun up or not
        :rtype: boolean
        """
        alive = self._pool.running() + self._pool.waiting()
        if alive < self._max_workers:
            self._pool.spawn_n(_green.GreenWorker(work, self._delayed_work))
            return True
        return False

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            if not self._shutdown:
                self._shutdown = True
                shutoff = True
            else:
                shutoff = False
        if wait and shutoff:
            self._delayed_work.join()
            self._pool.waitall()


class ExecutorStatistics(object):
    """Holds *immutable* information about a executors executions."""

    __slots__ = ['_failures', '_executed', '_runtime', '_cancelled']

    _REPR_MSG_TPL = ("<ExecutorStatistics object at 0x%(ident)x"
                     " (failures=%(failures)s,"
                     " executed=%(executed)s, runtime=%(runtime)0.2f,"
                     " cancelled=%(cancelled)s)>")

    def __init__(self, failures=0, executed=0, runtime=0.0, cancelled=0):
        self._failures = failures
        self._executed = executed
        self._runtime = runtime
        self._cancelled = cancelled

    @property
    def failures(self):
        """How many submissions ended up raising exceptions.

        :returns: how many submissions ended up raising exceptions
        :rtype: number
        """
        return self._failures

    @property
    def executed(self):
        """How many submissions were executed (failed or not).

        :returns: how many submissions were executed
        :rtype: number
        """
        return self._executed

    @property
    def runtime(self):
        """Total runtime of all submissions executed (failed or not).

        :returns: total runtime of all submissions executed
        :rtype: number
        """
        return self._runtime

    @property
    def cancelled(self):
        """How many submissions were cancelled before executing.

        :returns: how many submissions were cancelled before executing
        :rtype: number
        """
        return self._cancelled

    @property
    def average_runtime(self):
        """The average runtime of all submissions executed.

        :returns: average runtime of all submissions executed
        :rtype: number
        :raises: ZeroDivisionError when no executions have occurred.
        """
        return self._runtime / self._executed

    def __repr__(self):
        return self._REPR_MSG_TPL % ({
            'ident': id(self),
            'failures': self._failures,
            'executed': self._executed,
            'runtime': self._runtime,
            'cancelled': self._cancelled,
        })
