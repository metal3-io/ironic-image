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

try:
    from contextlib import ExitStack
except ImportError:
    from contextlib2 import ExitStack

import collections
import contextlib

from concurrent import futures
from concurrent.futures import _base
import six

import futurist
from futurist import _utils

try:
    from eventlet.green import threading as greenthreading
except ImportError:
    greenthreading = None


#: Named tuple returned from ``wait_for*`` calls.
DoneAndNotDoneFutures = collections.namedtuple(
    'DoneAndNotDoneFutures', 'done not_done')

_DONE_STATES = frozenset([
    _base.CANCELLED_AND_NOTIFIED,
    _base.FINISHED,
])


@contextlib.contextmanager
def _acquire_and_release_futures(fs):
    # Do this to ensure that we always get the futures in the same order (aka
    # always acquire the conditions in the same order, no matter what; a way
    # to avoid dead-lock).
    fs = sorted(fs, key=id)
    with ExitStack() as stack:
        for fut in fs:
            stack.enter_context(fut._condition)
        yield


def _ensure_eventlet(func):
    """Decorator that verifies we have the needed eventlet components."""

    @six.wraps(func)
    def wrapper(*args, **kwargs):
        if not _utils.EVENTLET_AVAILABLE or greenthreading is None:
            raise RuntimeError('Eventlet is needed to wait on green futures')
        return func(*args, **kwargs)

    return wrapper


def _wait_for(fs, no_green_return_when, on_all_green_cb,
              caller_name, timeout=None):
    green_fs = sum(1 for f in fs if isinstance(f, futurist.GreenFuture))
    if not green_fs:
        done, not_done = futures.wait(fs, timeout=timeout,
                                      return_when=no_green_return_when)
        return DoneAndNotDoneFutures(done, not_done)
    else:
        non_green_fs = len(fs) - green_fs
        if non_green_fs:
            raise RuntimeError("Can not wait on %s green futures and %s"
                               " non-green futures in the same"
                               " `%s` call" % (green_fs, non_green_fs,
                                               caller_name))
        else:
            return on_all_green_cb(fs, timeout=timeout)


def wait_for_all(fs, timeout=None):
    """Wait for all of the futures to complete.

    Works correctly with both green and non-green futures (but not both
    together, since this can't be guaranteed to avoid dead-lock due to how
    the waiting implementations are different when green threads are being
    used).

    Returns pair (done futures, not done futures).
    """
    return _wait_for(fs, futures.ALL_COMPLETED, _wait_for_all_green,
                     'wait_for_all', timeout=timeout)


def wait_for_any(fs, timeout=None):
    """Wait for one (**any**) of the futures to complete.

    Works correctly with both green and non-green futures (but not both
    together, since this can't be guaranteed to avoid dead-lock due to how
    the waiting implementations are different when green threads are being
    used).

    Returns pair (done futures, not done futures).
    """
    return _wait_for(fs, futures.FIRST_COMPLETED, _wait_for_any_green,
                     'wait_for_any', timeout=timeout)


class _AllGreenWaiter(object):
    """Provides the event that ``_wait_for_all_green`` blocks on."""

    def __init__(self, pending):
        self.event = greenthreading.Event()
        self.lock = greenthreading.Lock()
        self.pending = pending

    def _decrement_pending(self):
        with self.lock:
            self.pending -= 1
            if self.pending <= 0:
                self.event.set()

    def add_result(self, future):
        self._decrement_pending()

    def add_exception(self, future):
        self._decrement_pending()

    def add_cancelled(self, future):
        self._decrement_pending()


class _AnyGreenWaiter(object):
    """Provides the event that ``_wait_for_any_green`` blocks on."""

    def __init__(self):
        self.event = greenthreading.Event()

    def add_result(self, future):
        self.event.set()

    def add_exception(self, future):
        self.event.set()

    def add_cancelled(self, future):
        self.event.set()


def _partition_futures(fs):
    done = set()
    not_done = set()
    for f in fs:
        if f._state in _DONE_STATES:
            done.add(f)
        else:
            not_done.add(f)
    return done, not_done


def _create_and_install_waiters(fs, waiter_cls, *args, **kwargs):
    waiter = waiter_cls(*args, **kwargs)
    for f in fs:
        f._waiters.append(waiter)
    return waiter


@_ensure_eventlet
def _wait_for_all_green(fs, timeout=None):
    if not fs:
        return DoneAndNotDoneFutures(set(), set())

    with _acquire_and_release_futures(fs):
        done, not_done = _partition_futures(fs)
        if len(done) == len(fs):
            return DoneAndNotDoneFutures(done, not_done)
        waiter = _create_and_install_waiters(not_done,
                                             _AllGreenWaiter,
                                             len(not_done))
    waiter.event.wait(timeout)
    for f in not_done:
        f._waiters.remove(waiter)

    with _acquire_and_release_futures(fs):
        done, not_done = _partition_futures(fs)
        return DoneAndNotDoneFutures(done, not_done)


@_ensure_eventlet
def _wait_for_any_green(fs, timeout=None):
    if not fs:
        return DoneAndNotDoneFutures(set(), set())

    with _acquire_and_release_futures(fs):
        done, not_done = _partition_futures(fs)
        if done:
            return DoneAndNotDoneFutures(done, not_done)
        waiter = _create_and_install_waiters(fs, _AnyGreenWaiter)

    waiter.event.wait(timeout)
    for f in fs:
        f._waiters.remove(waiter)

    with _acquire_and_release_futures(fs):
        done, not_done = _partition_futures(fs)
        return DoneAndNotDoneFutures(done, not_done)
