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

import collections
import fractions
import functools
import heapq
import inspect
import logging
import math
import random
import threading

from concurrent import futures
import prettytable
import six

import futurist
from futurist import _utils as utils

LOG = logging.getLogger(__name__)


class NeverAgain(Exception):
    """Exception to raise to stop further periodic calls for a function.

    When you want a function never run again you can throw this from
    you periodic function and that will signify to the execution framework
    to remove that function (and never run it again).
    """


_REQUIRED_ATTRS = ('_is_periodic', '_periodic_spacing',
                   '_periodic_run_immediately')

_DEFAULT_COLS = ('Name', 'Active', 'Periodicity', 'Runs in',
                 'Runs', 'Failures', 'Successes', 'Stop Requested',
                 'Average elapsed', 'Average elapsed waiting')

# Constants that are used to determine what 'kind' the current callback
# is being ran as.
PERIODIC = 'periodic'
IMMEDIATE = 'immediate'


class Work(collections.namedtuple("Work",
                                  ['name', 'callback', 'args', 'kwargs'])):
    """Named unit of work that can be periodically scheduled and watched."""

    def __call__(self):
        return self.callback(*self.args, **self.kwargs)


class Watcher(object):
    """A **read-only** object representing a periodic callback's activities."""

    def __init__(self, metrics, work):
        self._metrics = metrics
        self._work = work

    def __repr__(self):
        return ("<Watcher(metrics=%(metrics)s, work=%(work)s)"
                " object at 0x%(ident)x>") % dict(ident=id(self),
                                                  work=self._work,
                                                  metrics=self._metrics)

    @property
    def requested_stop(self):
        """If the work unit being ran has requested to be stopped."""
        return self._metrics['requested_stop']

    @property
    def work(self):
        """**Read-only** named work tuple this object watches."""
        return self._work

    @property
    def runs(self):
        """How many times the periodic callback has been ran."""
        return self._metrics['runs']

    @property
    def successes(self):
        """How many times the periodic callback ran successfully."""
        return self._metrics['successes']

    @property
    def failures(self):
        """How many times the periodic callback ran unsuccessfully."""
        return self._metrics['failures']

    @property
    def elapsed(self):
        """Total amount of time the periodic callback has ran for."""
        return self._metrics['elapsed']

    @property
    def elapsed_waiting(self):
        """Total amount of time the periodic callback has waited to run for."""
        return self._metrics['elapsed_waiting']

    @property
    def average_elapsed_waiting(self):
        """Avg. amount of time the periodic callback has waited to run for.

        This may raise a ``ZeroDivisionError`` if there has been no runs.
        """
        return self._metrics['elapsed_waiting'] / self._metrics['runs']

    @property
    def average_elapsed(self):
        """Avg. amount of time the periodic callback has ran for.

        This may raise a ``ZeroDivisionError`` if there has been no runs.
        """
        return self._metrics['elapsed'] / self._metrics['runs']


def _check_attrs(obj):
    """Checks that a periodic function/method has all the expected attributes.

    This will return the expected attributes that were **not** found.
    """
    missing_attrs = []
    for attr_name in _REQUIRED_ATTRS:
        if not hasattr(obj, attr_name):
            missing_attrs.append(attr_name)
    return missing_attrs


def is_periodic(obj):
    """Check whether an object is a valid periodic callable.

    :param obj: object to inspect
    :type obj: anything
    :return: True if obj is a periodic task, otherwise False
    """
    return callable(obj) and not _check_attrs(obj)


def periodic(spacing, run_immediately=False, enabled=True):
    """Tags a method/function as wanting/able to execute periodically.

    :param spacing: how often to run the decorated function (required)
    :type spacing: float/int
    :param run_immediately: option to specify whether to run
                            immediately or wait until the spacing provided has
                            elapsed before running for the first time
    :type run_immediately: boolean
    :param enabled: whether the task is enabled to run
    :type enabled: boolean
    """

    if spacing <= 0 and enabled:
        raise ValueError("Periodicity/spacing must be greater than"
                         " zero instead of %s" % spacing)

    def wrapper(f):
        f._is_periodic = enabled
        f._periodic_spacing = spacing
        f._periodic_run_immediately = run_immediately

        @six.wraps(f)
        def decorator(*args, **kwargs):
            return f(*args, **kwargs)

        return decorator

    return wrapper


def _add_jitter(max_percent_jitter):
    """Wraps a existing strategy and adds jitter to it.

    0% to 100% of the spacing value will be added to this value to ensure
    callbacks do not synchronize.
    """
    if max_percent_jitter > 1 or max_percent_jitter < 0:
        raise ValueError("Invalid 'max_percent_jitter', must be greater or"
                         " equal to 0.0 and less than or equal to 1.0")

    def wrapper(func):
        rnd = random.SystemRandom()

        @six.wraps(func)
        def decorator(cb, started_at, finished_at, metrics):
            next_run = func(cb, started_at, finished_at, metrics)
            how_often = cb._periodic_spacing
            jitter = how_often * (rnd.random() * max_percent_jitter)
            return next_run + jitter

        decorator.__name__ += "_with_jitter"
        return decorator

    return wrapper


def _last_finished_strategy(cb, started_at, finished_at, metrics):
    # Determine when the callback should next run based on when it was
    # last finished **only** given metrics about this information.
    how_often = cb._periodic_spacing
    return finished_at + how_often


def _last_started_strategy(cb, started_at, finished_at, metrics):
    # Determine when the callback should next run based on when it was
    # last started **only** given metrics about this information.
    how_often = cb._periodic_spacing
    return started_at + how_often


def _aligned_last_finished_strategy(cb, started_at, finished_at, metrics):
    # Determine when the callback should next run based on when it was
    # last finished **only** where the last finished time is first aligned to
    # be a multiple of the expected spacing (so that no matter how long or
    # how short the callback takes it is always ran on its next aligned
    # to spacing time).
    how_often = cb._periodic_spacing
    aligned_finished_at = finished_at - math.fmod(finished_at, how_often)
    return aligned_finished_at + how_often


def _now_plus_periodicity(cb, now):
    how_often = cb._periodic_spacing
    return how_often + now


class _Schedule(object):
    """Internal heap-based structure that maintains the schedule/ordering.

    This stores a heap composed of the following ``(next_run, index)`` where
    ``next_run`` is the next desired runtime for the callback that is stored
    somewhere with the index provided. The index is saved so that if two
    functions with the same ``next_run`` time are inserted, that the one with
    the smaller index is preferred (it is also saved so that on pop we can
    know what the index of the callback we should call is).
    """

    def __init__(self):
        self._ordering = []

    def push(self, next_run, index):
        heapq.heappush(self._ordering, (next_run, index))

    def __len__(self):
        return len(self._ordering)

    def fetch_next_run(self, index):
        for (next_run, a_index) in self._ordering:
            if a_index == index:
                return next_run
        return None

    def pop(self):
        return heapq.heappop(self._ordering)


def _on_failure_log(log, cb, kind, spacing, exc_info, traceback=None):
    cb_name = utils.get_callback_name(cb)
    if all(exc_info) or not traceback:
        log.error("Failed to call %s '%s' (it runs every %0.2f"
                  " seconds)", kind, cb_name, spacing, exc_info=exc_info)
    else:
        log.error("Failed to call %s '%s' (it runs every %0.2f"
                  " seconds):\n%s", kind, cb_name, spacing, traceback)


class _Runner(object):
    def __init__(self, now_func, retain_traceback=True):
        self.now_func = now_func
        self.retain_traceback = retain_traceback

    def run(self, work):
        failure = None
        started_at = self.now_func()
        try:
            work()
        except Exception:
            # Until https://bugs.python.org/issue24451 is merged we have to
            # capture and return the failure, so that we can have reliable
            # timing information.
            failure = utils.Failure(self.retain_traceback)
        finished_at = self.now_func()
        return (started_at, finished_at, failure)


def _build(now_func, works, next_run_scheduler):
    schedule = _Schedule()
    now = None
    immediates = collections.deque()
    for index, work in enumerate(works):
        cb = work.callback
        if cb._periodic_run_immediately:
            immediates.append(index)
        else:
            if now is None:
                now = now_func()
            next_run = next_run_scheduler(cb, now)
            schedule.push(next_run, index)
    return immediates, schedule


_SCHEDULE_RETRY_EXCEPTIONS = (RuntimeError, futurist.RejectedSubmission)


class ExecutorFactory(object):
    """Base class for any executor factory."""

    shutdown = True
    """Whether the executor should be shut down on periodic worker stop."""

    def __call__(self):
        """Return the executor to be used."""
        raise NotImplementedError()


class ExistingExecutor(ExecutorFactory):
    """An executor factory returning the existing object."""

    def __init__(self, executor, shutdown=False):
        self._executor = executor
        self.shutdown = shutdown

    def __call__(self):
        return self._executor


class PeriodicWorker(object):
    """Calls a collection of callables periodically (sleeping as needed...).

    NOTE(harlowja): typically the :py:meth:`.start` method is executed in a
    background thread so that the periodic callables are executed in
    the background/asynchronously (using the defined periods to determine
    when each is called).
    """

    #: Max amount of time to wait when running (forces a wakeup when elapsed).
    MAX_LOOP_IDLE = 30

    _NO_OP_ARGS = ()
    _NO_OP_KWARGS = {}
    _INITIAL_METRICS = {
        'runs': 0,
        'elapsed': 0,
        'elapsed_waiting': 0,
        'failures': 0,
        'successes': 0,
        'requested_stop': False,
    }

    # When scheduling fails temporary, use a random delay between 0.9-1.1 sec.
    _RESCHEDULE_DELAY = 0.9
    _RESCHEDULE_JITTER = 0.2

    DEFAULT_JITTER = fractions.Fraction(5, 100)
    """
    Default jitter percentage the built-in strategies (that have jitter
    support) will use.
    """

    BUILT_IN_STRATEGIES = {
        'last_started': (
            _last_started_strategy,
            _now_plus_periodicity,
        ),
        'last_started_jitter': (
            _add_jitter(DEFAULT_JITTER)(_last_started_strategy),
            _now_plus_periodicity,
        ),
        'last_finished': (
            _last_finished_strategy,
            _now_plus_periodicity,
        ),
        'last_finished_jitter': (
            _add_jitter(DEFAULT_JITTER)(_last_finished_strategy),
            _now_plus_periodicity,
        ),
        'aligned_last_finished': (
            _aligned_last_finished_strategy,
            _now_plus_periodicity,
        ),
        'aligned_last_finished_jitter': (
            _add_jitter(DEFAULT_JITTER)(_aligned_last_finished_strategy),
            _now_plus_periodicity,
        ),
    }
    """
    Built in scheduling strategies (used to determine when next to run
    a periodic callable).

    The first element is the strategy to use after the initial start
    and the second element is the strategy to use for the initial start.

    These are made somewhat pluggable so that we can *easily* add-on
    different types later (perhaps one that uses a cron-style syntax
    for example).
    """

    @classmethod
    def create(cls, objects, exclude_hidden=True,
               log=None, executor_factory=None,
               cond_cls=threading.Condition, event_cls=threading.Event,
               schedule_strategy='last_started', now_func=utils.now,
               on_failure=None, args=_NO_OP_ARGS, kwargs=_NO_OP_KWARGS):
        """Automatically creates a worker by analyzing object(s) methods.

        Only picks up methods that have been tagged/decorated with
        the :py:func:`.periodic` decorator (does not match against private
        or protected methods unless explicitly requested to).

        :param objects: the objects to introspect for decorated members
        :type objects: iterable
        :param exclude_hidden: exclude hidden members (ones that start with
                               an underscore)
        :type exclude_hidden: bool
        :param log: logger to use when creating a new worker (defaults
                    to the module logger if none provided), it is currently
                    only used to report callback failures (if they occur)
        :type log: logger
        :param executor_factory: factory callable that can be used to generate
                                 executor objects that will be used to
                                 run the periodic callables (if none is
                                 provided one will be created that uses
                                 the :py:class:`~futurist.SynchronousExecutor`
                                 class)
        :type executor_factory: ExecutorFactory or any callable
        :param cond_cls: callable object that can
                          produce ``threading.Condition``
                          (or compatible/equivalent) objects
        :type cond_cls: callable
        :param event_cls: callable object that can produce ``threading.Event``
                          (or compatible/equivalent) objects
        :type event_cls: callable
        :param schedule_strategy: string to select one of the built-in
                                  strategies that can return the
                                  next time a callable should run
        :type schedule_strategy: string
        :param now_func: callable that can return the current time offset
                         from some point (used in calculating elapsed times
                         and next times to run); preferably this is
                         monotonically increasing
        :type now_func: callable
        :param on_failure: callable that will be called whenever a periodic
                           function fails with an error, it will be provided
                           four positional arguments and one keyword
                           argument, the first positional argument being the
                           callable that failed, the second being the type
                           of activity under which it failed (``IMMEDIATE`` or
                           ``PERIODIC``), the third being the spacing that the
                           callable runs at and the fourth ``exc_info`` tuple
                           of the failure. The keyword argument ``traceback``
                           will also be provided that may be be a string
                           that caused the failure (this is required for
                           executors which run out of process, as those can not
                           *currently* transfer stack frames across process
                           boundaries); if no callable is provided then a
                           default failure logging function will be used
                           instead (do note that
                           any user provided callable should not raise
                           exceptions on being called)
        :type on_failure: callable
        :param args: positional arguments to be passed to all callables
        :type args: tuple
        :param kwargs: keyword arguments to be passed to all callables
        :type kwargs: dict
        """
        callables = []
        for obj in objects:
            for (name, member) in inspect.getmembers(obj):
                if name.startswith("_") and exclude_hidden:
                    continue
                if six.callable(member):
                    missing_attrs = _check_attrs(member)
                    if not missing_attrs:
                        callables.append((member, args, kwargs))
        return cls(callables, log=log, executor_factory=executor_factory,
                   cond_cls=cond_cls, event_cls=event_cls,
                   schedule_strategy=schedule_strategy, now_func=now_func,
                   on_failure=on_failure)

    def __init__(self, callables, log=None, executor_factory=None,
                 cond_cls=threading.Condition, event_cls=threading.Event,
                 schedule_strategy='last_started', now_func=utils.now,
                 on_failure=None):
        """Creates a new worker using the given periodic callables.

        :param callables: a iterable of tuple objects previously decorated
                          with the :py:func:`.periodic` decorator, each item
                          in the iterable is expected to be in the format
                          of ``(cb, args, kwargs)`` where ``cb`` is the
                          decorated function and ``args`` and ``kwargs`` are
                          any positional and keyword arguments to send into
                          the callback when it is activated (both ``args``
                          and ``kwargs`` may be provided as none to avoid
                          using them)
        :type callables: iterable
        :param log: logger to use when creating a new worker (defaults
                    to the module logger if none provided), it is currently
                    only used to report callback failures (if they occur)
        :type log: logger
        :param executor_factory: factory callable that can be used to generate
                                 executor objects that will be used to
                                 run the periodic callables (if none is
                                 provided one will be created that uses
                                 the :py:class:`~futurist.SynchronousExecutor`
                                 class)
        :type executor_factory: ExecutorFactory or any callable
        :param cond_cls: callable object that can
                          produce ``threading.Condition``
                          (or compatible/equivalent) objects
        :type cond_cls: callable
        :param event_cls: callable object that can produce ``threading.Event``
                          (or compatible/equivalent) objects
        :type event_cls: callable
        :param schedule_strategy: string to select one of the built-in
                                  strategies that can return the
                                  next time a callable should run
        :type schedule_strategy: string
        :param now_func: callable that can return the current time offset
                         from some point (used in calculating elapsed times
                         and next times to run); preferably this is
                         monotonically increasing
        :type now_func: callable
        :param on_failure: callable that will be called whenever a periodic
                           function fails with an error, it will be provided
                           four positional arguments and one keyword
                           argument, the first positional argument being the
                           callable that failed, the second being the type
                           of activity under which it failed (``IMMEDIATE`` or
                           ``PERIODIC``), the third being the spacing that the
                           callable runs at and the fourth ``exc_info`` tuple
                           of the failure. The keyword argument ``traceback``
                           will also be provided that may be be a string
                           that caused the failure (this is required for
                           executors which run out of process, as those can not
                           *currently* transfer stack frames across process
                           boundaries); if no callable is provided then a
                           default failure logging function will be used
                           instead (do note that
                           any user provided callable should not raise
                           exceptions on being called)
        :type on_failure: callable
        """
        if on_failure is not None and not six.callable(on_failure):
            raise ValueError("On failure callback %r must be"
                             " callable" % on_failure)
        self._tombstone = event_cls()
        self._waiter = cond_cls()
        self._dead = event_cls()
        self._active = event_cls()
        self._cond_cls = cond_cls
        self._watchers = []
        self._works = []
        for (cb, args, kwargs) in callables:
            if not six.callable(cb):
                raise ValueError("Periodic callback %r must be callable" % cb)
            missing_attrs = _check_attrs(cb)
            if missing_attrs:
                raise ValueError("Periodic callback %r missing required"
                                 " attributes %s" % (cb, missing_attrs))
            if cb._is_periodic:
                # Ensure these aren't none and if so replace them with
                # something more appropriate...
                if args is None:
                    args = self._NO_OP_ARGS
                if kwargs is None:
                    kwargs = self._NO_OP_KWARGS.copy()
                cb_metrics = self._INITIAL_METRICS.copy()
                work = Work(utils.get_callback_name(cb), cb, args, kwargs)
                watcher = Watcher(cb_metrics, work)
                self._works.append(work)
                self._watchers.append((cb_metrics, watcher))
        try:
            strategy = self.BUILT_IN_STRATEGIES[schedule_strategy]
            self._schedule_strategy = strategy[0]
            self._initial_schedule_strategy = strategy[1]
        except KeyError:
            valid_strategies = sorted(self.BUILT_IN_STRATEGIES.keys())
            raise ValueError("Scheduling strategy '%s' must be one of"
                             " %s selectable strategies"
                             % (schedule_strategy, valid_strategies))
        self._immediates, self._schedule = _build(
            now_func, self._works, self._initial_schedule_strategy)
        self._log = log or LOG
        if executor_factory is None:
            executor_factory = lambda: futurist.SynchronousExecutor()
        if on_failure is None:
            on_failure = functools.partial(_on_failure_log, self._log)
        self._on_failure = on_failure
        self._executor_factory = executor_factory
        self._now_func = now_func

    def __len__(self):
        """How many callables/periodic work units are currently active."""
        return len(self._works)

    def _run(self, executor, runner, auto_stop_when_empty):
        """Main worker run loop."""
        barrier = utils.Barrier(cond_cls=self._cond_cls)
        rnd = random.SystemRandom()

        def _process_scheduled():
            # Figure out when we should run next (by selecting the
            # minimum item from the heap, where the minimum should be
            # the callable that needs to run next and has the lowest
            # next desired run time).
            with self._waiter:
                while (not self._schedule and
                       not self._tombstone.is_set() and
                       not self._immediates):
                    self._waiter.wait(self.MAX_LOOP_IDLE)
                if self._tombstone.is_set():
                    # We were requested to stop, so stop.
                    return
                if self._immediates:
                    # This will get processed in _process_immediates()
                    # in the next loop call.
                    return
                submitted_at = now = self._now_func()
                next_run, index = self._schedule.pop()
                when_next = next_run - now
                if when_next <= 0:
                    # Run & schedule its next execution.
                    work = self._works[index]
                    self._log.debug("Submitting periodic"
                                    " callback '%s'", work.name)
                    try:
                        fut = executor.submit(runner.run, work)
                    except _SCHEDULE_RETRY_EXCEPTIONS as exc:
                        # Restart after a short delay
                        delay = (self._RESCHEDULE_DELAY +
                                 rnd.random() * self._RESCHEDULE_JITTER)
                        self._log.error("Failed to submit periodic callback "
                                        "'%s', retrying after %.2f sec. "
                                        "Error: %s",
                                        work.name, delay, exc)
                        self._schedule.push(self._now_func() + delay,
                                            index)
                    else:
                        barrier.incr()
                        fut.add_done_callback(functools.partial(_on_done,
                                                                PERIODIC,
                                                                work, index,
                                                                submitted_at))
                else:
                    # Gotta wait...
                    self._schedule.push(next_run, index)
                    when_next = min(when_next, self.MAX_LOOP_IDLE)
                    self._waiter.wait(when_next)

        def _process_immediates():
            with self._waiter:
                try:
                    index = self._immediates.popleft()
                except IndexError:
                    pass
                else:
                    work = self._works[index]
                    submitted_at = self._now_func()
                    self._log.debug("Submitting immediate"
                                    " callback '%s'", work.name)
                    try:
                        fut = executor.submit(runner.run, work)
                    except _SCHEDULE_RETRY_EXCEPTIONS as exc:
                        self._log.error("Failed to submit immediate callback "
                                        "'%s', retrying. Error: %s", work.name,
                                        exc)
                        # Restart as soon as possible
                        self._immediates.append(index)
                    else:
                        barrier.incr()
                        fut.add_done_callback(functools.partial(_on_done,
                                                                IMMEDIATE,
                                                                work, index,
                                                                submitted_at))

        def _on_done(kind, work, index, submitted_at, fut):
            cb = work.callback
            started_at, finished_at, failure = fut.result()
            cb_metrics, _watcher = self._watchers[index]
            cb_metrics['runs'] += 1
            schedule_again = True
            if failure is not None:
                if not issubclass(failure.exc_type, NeverAgain):
                    cb_metrics['failures'] += 1
                    try:
                        self._on_failure(cb, kind, cb._periodic_spacing,
                                         failure.exc_info,
                                         traceback=failure.traceback)
                    except Exception as exc:
                        self._log.error("On failure callback %r raised an"
                                        " unhandled exception. Error: %s",
                                        self._on_failure, exc)
                else:
                    cb_metrics['successes'] += 1
                    schedule_again = False
                    self._log.debug("Periodic callback '%s' raised "
                                    "'NeverAgain' "
                                    "exception, stopping any further "
                                    "execution of it.", work.name)
            else:
                cb_metrics['successes'] += 1
            elapsed = max(0, finished_at - started_at)
            elapsed_waiting = max(0, started_at - submitted_at)
            cb_metrics['elapsed'] += elapsed
            cb_metrics['elapsed_waiting'] += elapsed_waiting
            with self._waiter:
                with barrier.decr_cm() as am_left:
                    if schedule_again:
                        next_run = self._schedule_strategy(cb, started_at,
                                                           finished_at,
                                                           cb_metrics)
                        self._schedule.push(next_run, index)
                    else:
                        cb_metrics['requested_stop'] = True
                        if (am_left <= 0 and
                                len(self._immediates) == 0 and
                                len(self._schedule) == 0 and
                                auto_stop_when_empty):
                            # Guess nothing left to do, goodbye...
                            self._tombstone.set()
                self._waiter.notify_all()

        try:
            while not self._tombstone.is_set():
                _process_immediates()
                _process_scheduled()
        finally:
            barrier.wait()

    def _on_finish(self):
        # TODO(harlowja): this may be to verbose for people?
        if not self._log.isEnabledFor(logging.DEBUG):
            return
        cols = list(_DEFAULT_COLS)
        for c in ['Runs in', 'Active', 'Periodicity']:
            cols.remove(c)
        self._log.debug("Stopped running %s callbacks:\n%s",
                        len(self._works), self.pformat(columns=cols))

    def pformat(self, columns=_DEFAULT_COLS):
        # Convert to a list to ensure we maintain the same order when used
        # further in this function (since order will matter)...
        if not isinstance(columns, (list, tuple)):
            columns = list(columns)
        if not columns:
            raise ValueError("At least one of %s columns must"
                             " be provided" % (set(_DEFAULT_COLS)))
        for c in columns:
            if c not in _DEFAULT_COLS:
                raise ValueError("Unknown column '%s', valid column names"
                                 " are %s" % (c, set(_DEFAULT_COLS)))
        tbl_rows = []
        now = self._now_func()
        for index, work in enumerate(self._works):
            _cb_metrics, watcher = self._watchers[index]
            next_run = self._schedule.fetch_next_run(index)
            if watcher.requested_stop:
                active = False
                runs_in = 'n/a'
            elif next_run is None:
                active = True
                runs_in = 'n/a'
            else:
                active = False
                runs_in = "%0.4fs" % (max(0.0, next_run - now))
            cb_row = {
                'Name': work.name,
                'Active': active,
                'Periodicity': work.callback._periodic_spacing,
                'Runs': watcher.runs,
                'Runs in': runs_in,
                'Failures': watcher.failures,
                'Successes': watcher.successes,
                'Stop Requested': watcher.requested_stop,
            }
            try:
                cb_row_avgs = [
                    "%0.4fs" % watcher.average_elapsed,
                    "%0.4fs" % watcher.average_elapsed_waiting,
                ]
            except ZeroDivisionError:
                cb_row_avgs = ['.', '.']
            cb_row['Average elapsed'] = cb_row_avgs[0]
            cb_row['Average elapsed waiting'] = cb_row_avgs[1]
            tbl_rows.append(cb_row)
        # Now form the table, but use only the columns that the caller
        # asked for (and in the order they asked for...)
        tbl = prettytable.PrettyTable(columns)
        for cb_row in tbl_rows:
            tbl_row = []
            for c in columns:
                tbl_row.append(cb_row[c])
            tbl.add_row(tbl_row)
        return tbl.get_string()

    def add(self, cb, *args, **kwargs):
        """Adds a new periodic callback to the current worker.

        Returns a :py:class:`.Watcher` if added successfully or the value
        ``None`` if not (or raises a ``ValueError`` if the callback is not
        correctly formed and/or decorated).

        :param cb: a callable object/method/function previously decorated
                   with the :py:func:`.periodic` decorator
        :type cb: callable
        """
        if not six.callable(cb):
            raise ValueError("Periodic callback %r must be callable" % cb)
        missing_attrs = _check_attrs(cb)
        if missing_attrs:
            raise ValueError("Periodic callback %r missing required"
                             " attributes %s" % (cb, missing_attrs))
        if not cb._is_periodic:
            return None
        now = self._now_func()
        with self._waiter:
            cb_index = len(self._works)
            cb_metrics = self._INITIAL_METRICS.copy()
            work = Work(utils.get_callback_name(cb), cb, args, kwargs)
            watcher = Watcher(cb_metrics, work)
            self._works.append(work)
            self._watchers.append((cb_metrics, watcher))
            if cb._periodic_run_immediately:
                self._immediates.append(cb_index)
            else:
                next_run = self._initial_schedule_strategy(cb, now)
                self._schedule.push(next_run, cb_index)
            self._waiter.notify_all()
            return watcher

    def start(self, allow_empty=False, auto_stop_when_empty=False):
        """Starts running (will not return until :py:meth:`.stop` is called).

        :param allow_empty: instead of running with no callbacks raise when
                            this worker has no contained callables (this can be
                            set to true and :py:meth:`.add` can be used to add
                            new callables on demand), note that when enabled
                            and no callbacks exist this will block and
                            sleep (until either stopped or callbacks are
                            added)
        :type allow_empty: bool
        :param auto_stop_when_empty: when the provided periodic functions have
                                     all exited and this is false then the
                                     thread responsible for executing those
                                     methods will just spin/idle waiting for
                                     a new periodic function to be added;
                                     switching it to true will make this
                                     idling not happen (and instead when no
                                     more periodic work exists then the
                                     calling thread will just return).
        :type auto_stop_when_empty: bool
        """
        if not self._works and not allow_empty:
            raise RuntimeError("A periodic worker can not start"
                               " without any callables to process")
        if self._active.is_set():
            raise RuntimeError("A periodic worker can not be started"
                               " twice")
        executor = self._executor_factory()
        # NOTE(harlowja): we compare with the futures process pool executor
        # since its the base type of futurist ProcessPoolExecutor and it is
        # possible for users to pass in there own custom executors, this one
        # is known to not be able to retain tracebacks...
        if isinstance(executor, futures.ProcessPoolExecutor):
            # Pickling a traceback will not work, so do not try to do it...
            #
            # Avoids 'TypeError: can't pickle traceback objects'
            runner = _Runner(self._now_func, retain_traceback=False)
        else:
            runner = _Runner(self._now_func, retain_traceback=True)
        self._dead.clear()
        self._active.set()
        try:
            self._run(executor, runner, auto_stop_when_empty)
        finally:
            if getattr(self._executor_factory, 'shutdown', True):
                executor.shutdown()
            self._dead.set()
            self._active.clear()
            self._on_finish()

    def stop(self):
        """Sets the tombstone (this stops any further executions)."""
        with self._waiter:
            self._tombstone.set()
            self._waiter.notify_all()

    def iter_watchers(self):
        """Iterator/generator over all the currently maintained watchers."""
        for _cb_metrics, watcher in self._watchers:
            yield watcher

    def reset(self):
        """Resets the workers internal state."""
        self._tombstone.clear()
        self._dead.clear()
        for cb_metrics, _watcher in self._watchers:
            for k in list(six.iterkeys(cb_metrics)):
                # NOTE(harlowja): mutate the original dictionaries keys
                # so that the watcher (which references the same dictionary
                # keys) is able to see those changes.
                cb_metrics[k] = 0
        self._immediates, self._schedule = _build(
            self._now_func, self._works, self._initial_schedule_strategy)

    def wait(self, timeout=None):
        """Waits for the :py:meth:`.start` method to gracefully exit.

        An optional timeout can be provided, which will cause the method to
        return within the specified timeout. If the timeout is reached, the
        returned value will be False.

        :param timeout: Maximum number of seconds that the :meth:`.wait`
                        method should block for
        :type timeout: float/int
        """
        self._dead.wait(timeout)
        return self._dead.is_set()
