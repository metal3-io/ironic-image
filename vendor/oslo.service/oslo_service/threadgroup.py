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

import logging
import threading
import warnings

from debtcollector import removals
import eventlet
from eventlet import greenpool

from oslo_service import loopingcall
from oslo_utils import timeutils

LOG = logging.getLogger(__name__)


def _on_thread_done(_greenthread, group, thread):
    """Callback function to be passed to GreenThread.link() when we spawn().

    Calls the :class:`ThreadGroup` to notify it to remove this thread from
    the associated group.
    """
    group.thread_done(thread)


class Thread(object):
    """Wrapper around a greenthread.

     Holds a reference to the :class:`ThreadGroup`. The Thread will notify
     the :class:`ThreadGroup` when it has done so it can be removed from
     the threads list.
    """
    def __init__(self, thread, group, link=True):
        self.thread = thread
        if link:
            self.thread.link(_on_thread_done, group, self)
        self._ident = id(thread)

    @property
    def ident(self):
        return self._ident

    def stop(self):
        """Kill the thread by raising GreenletExit within it."""
        self.thread.kill()

    def wait(self):
        """Block until the thread completes and return the result."""
        return self.thread.wait()

    def link(self, func, *args, **kwargs):
        """Schedule a function to be run upon completion of the thread."""
        self.thread.link(func, *args, **kwargs)

    def cancel(self, *throw_args):
        """Prevent the thread from starting if it has not already done so.

        :param throw_args: the `exc_info` data to raise from :func:`wait`.
        """
        self.thread.cancel(*throw_args)


class ThreadGroup(object):
    """A group of greenthreads and timers.

    The point of the ThreadGroup class is to:

    * keep track of timers and greenthreads (making it easier to stop them
      when need be).
    * provide an easy API to add timers.

    .. note::
        The API is inconsistent, confusing, and not orthogonal. The same verbs
        often mean different things when applied to timers and threads,
        respectively. Read the documentation carefully.
    """

    def __init__(self, thread_pool_size=10):
        """Create a ThreadGroup with a pool of greenthreads.

        :param thread_pool_size: the maximum number of threads allowed to run
                                 concurrently.
        """
        self.pool = greenpool.GreenPool(thread_pool_size)
        self.threads = []
        self.timers = []

    def add_dynamic_timer(self, callback, initial_delay=None,
                          periodic_interval_max=None, *args, **kwargs):
        """Add a timer that controls its own period dynamically.

        The period of each iteration of the timer is controlled by the return
        value of the callback function on the previous iteration.

        .. warning::
            Passing arguments to the callback function is deprecated. Use the
            :func:`add_dynamic_timer_args` method to pass arguments for the
            callback function.

        :param callback: The callback function to run when the timer is
                         triggered.
        :param initial_delay: The delay in seconds before first triggering the
                              timer. If not set, the timer is liable to be
                              scheduled immediately.
        :param periodic_interval_max: The maximum interval in seconds to allow
                                      the callback function to request. If
                                      provided, this is also used as the
                                      default delay if None is returned by the
                                      callback function.
        :returns: an :class:`oslo_service.loopingcall.DynamicLoopingCall`
                  instance
        """
        if args or kwargs:
            warnings.warn("Calling add_dynamic_timer() with arguments to the "
                          "callback function is deprecated. Use "
                          "add_dynamic_timer_args() instead.",
                          DeprecationWarning)
        return self.add_dynamic_timer_args(
            callback, args, kwargs,
            initial_delay=initial_delay,
            periodic_interval_max=periodic_interval_max)

    def add_dynamic_timer_args(self, callback, args=None, kwargs=None,
                               initial_delay=None, periodic_interval_max=None,
                               stop_on_exception=True):
        """Add a timer that controls its own period dynamically.

        The period of each iteration of the timer is controlled by the return
        value of the callback function on the previous iteration.

        :param callback: The callback function to run when the timer is
                         triggered.
        :param args: A list of positional args to the callback function.
        :param kwargs: A dict of keyword args to the callback function.
        :param initial_delay: The delay in seconds before first triggering the
                              timer. If not set, the timer is liable to be
                              scheduled immediately.
        :param periodic_interval_max: The maximum interval in seconds to allow
                                      the callback function to request. If
                                      provided, this is also used as the
                                      default delay if None is returned by the
                                      callback function.
        :param stop_on_exception: Pass ``False`` to have the timer continue
                                  running even if the callback function raises
                                  an exception.
        :returns: an :class:`oslo_service.loopingcall.DynamicLoopingCall`
                  instance
        """
        args = args or []
        kwargs = kwargs or {}
        timer = loopingcall.DynamicLoopingCall(callback, *args, **kwargs)
        timer.start(initial_delay=initial_delay,
                    periodic_interval_max=periodic_interval_max,
                    stop_on_exception=stop_on_exception)
        self.timers.append(timer)
        return timer

    def add_timer(self, interval, callback, initial_delay=None,
                  *args, **kwargs):
        """Add a timer with a fixed period.

        .. warning::
            Passing arguments to the callback function is deprecated. Use the
            :func:`add_timer_args` method to pass arguments for the callback
            function.

        :param interval: The minimum period in seconds between calls to the
                         callback function.
        :param callback: The callback function to run when the timer is
                         triggered.
        :param initial_delay: The delay in seconds before first triggering the
                              timer. If not set, the timer is liable to be
                              scheduled immediately.
        :returns: an :class:`oslo_service.loopingcall.FixedIntervalLoopingCall`
                  instance
        """
        if args or kwargs:
            warnings.warn("Calling add_timer() with arguments to the callback "
                          "function is deprecated. Use add_timer_args() "
                          "instead.",
                          DeprecationWarning)
        return self.add_timer_args(interval, callback, args, kwargs,
                                   initial_delay=initial_delay)

    def add_timer_args(self, interval, callback, args=None, kwargs=None,
                       initial_delay=None, stop_on_exception=True):
        """Add a timer with a fixed period.

        :param interval: The minimum period in seconds between calls to the
                         callback function.
        :param callback: The callback function to run when the timer is
                         triggered.
        :param args: A list of positional args to the callback function.
        :param kwargs: A dict of keyword args to the callback function.
        :param initial_delay: The delay in seconds before first triggering the
                              timer. If not set, the timer is liable to be
                              scheduled immediately.
        :param stop_on_exception: Pass ``False`` to have the timer continue
                                  running even if the callback function raises
                                  an exception.
        :returns: an :class:`oslo_service.loopingcall.FixedIntervalLoopingCall`
                  instance
        """
        args = args or []
        kwargs = kwargs or {}
        pulse = loopingcall.FixedIntervalLoopingCall(callback, *args, **kwargs)
        pulse.start(interval=interval,
                    initial_delay=initial_delay,
                    stop_on_exception=stop_on_exception)
        self.timers.append(pulse)
        return pulse

    def add_thread(self, callback, *args, **kwargs):
        """Spawn a new thread.

        This call will block until capacity is available in the thread pool.
        After that, it returns immediately (i.e. *before* the new thread is
        scheduled).

        :param callback: the function to run in the new thread.
        :param args: positional arguments to the callback function.
        :param kwargs: keyword arguments to the callback function.
        :returns: a :class:`Thread` object
        """
        gt = self.pool.spawn(callback, *args, **kwargs)
        th = Thread(gt, self, link=False)
        self.threads.append(th)
        gt.link(_on_thread_done, self, th)
        return th

    def thread_done(self, thread):
        """Remove a completed thread from the group.

        This method is automatically called on completion of a thread in the
        group, and should not be called explicitly.
        """
        self.threads.remove(thread)

    def timer_done(self, timer):
        """Remove a timer from the group.

        :param timer: The timer object returned from :func:`add_timer` or its
                      analogues.
        """
        self.timers.remove(timer)

    def _perform_action_on_threads(self, action_func, on_error_func):
        current = threading.current_thread()
        # Iterate over a copy of self.threads so thread_done doesn't
        # modify the list while we're iterating
        for x in self.threads[:]:
            if x.ident == current.ident:
                # Don't perform actions on the current thread.
                continue
            try:
                action_func(x)
            except eventlet.greenlet.GreenletExit:  # nosec
                # greenlet exited successfully
                pass
            except Exception:
                on_error_func(x)

    def _stop_threads(self):
        self._perform_action_on_threads(
            lambda x: x.stop(),
            lambda x: LOG.exception('Error stopping thread.'))

    def stop_timers(self, wait=False):
        """Stop all timers in the group and remove them from the group.

        No new invocations of timers will be triggered after they are stopped,
        but calls that are in progress will not be interrupted.

        To wait for in-progress calls to complete, pass ``wait=True`` - calling
        :func:`wait` will not have the desired effect as the timers will have
        already been removed from the group.

        :param wait: If true, block until all timers have been stopped before
                     returning.
        """
        for timer in self.timers:
            timer.stop()
        if wait:
            self._wait_timers()
        self.timers = []

    def stop(self, graceful=False):
        """Stop all timers and threads in the group.

        No new invocations of timers will be triggered after they are stopped,
        but calls that are in progress will not be interrupted.

        If ``graceful`` is false, kill all threads immediately by raising
        GreenletExit. Note that in this case, this method will **not** block
        until all threads and running timer callbacks have actually exited. To
        guarantee that all threads have exited, call :func:`wait`.

        If ``graceful`` is true, do not kill threads. Block until all threads
        and running timer callbacks have completed. This is equivalent to
        calling :func:`stop_timers` with ``wait=True`` followed by
        :func:`wait`.

        :param graceful: If true, block until all timers have stopped and all
                         threads completed; never kill threads. Otherwise,
                         kill threads immediately and return immediately even
                         if there are timer callbacks still running.
        """
        self.stop_timers(wait=graceful)
        if graceful:
            # In case of graceful=True, wait for all threads to be
            # finished, never kill threads
            self._wait_threads()
        else:
            # In case of graceful=False(Default), kill threads
            # immediately
            self._stop_threads()

    def _wait_timers(self):
        for x in self.timers:
            try:
                x.wait()
            except eventlet.greenlet.GreenletExit:  # nosec
                # greenlet exited successfully
                pass
            except Exception:
                LOG.exception('Error waiting on timer.')

    def _wait_threads(self):
        self._perform_action_on_threads(
            lambda x: x.wait(),
            lambda x: LOG.exception('Error waiting on thread.'))

    def wait(self):
        """Block until all timers and threads in the group are complete.

        .. note::
            Before calling this method, any timers should be stopped first by
            calling :func:`stop_timers`, :func:`stop`, or :func:`cancel` with a
            ``timeout`` argument. Otherwise this will block forever.

        .. note::
            Calling :func:`stop_timers` removes the timers from the group, so a
            subsequent call to this method will not wait for any in-progress
            timer calls to complete.

        Any exceptions raised by the threads will be logged but suppressed.

        .. note::
            This call guarantees only that the threads themselves have
            completed, **not** that any cleanup functions added via
            :func:`Thread.link` have completed.
        """
        self._wait_timers()
        self._wait_threads()

    def _any_threads_alive(self):
        current = threading.current_thread()
        for x in self.threads[:]:
            if x.ident == current.ident:
                # Don't check current thread.
                continue
            if not x.thread.dead:
                return True
        return False

    @removals.remove(removal_version='?')
    def cancel(self, *throw_args, **kwargs):
        """Cancel unstarted threads in the group, and optionally stop the rest.

        .. warning::
            This method is deprecated and should not be used. It will be
            removed in a future release.

        If called without the ``timeout`` argument, this does **not** stop any
        running threads, but prevents any threads in the group that have not
        yet started from running, then returns immediately. Timers are not
        affected.

        If the 'timeout' argument is supplied, then it serves as a grace period
        to allow running threads to finish. After the timeout, any threads in
        the group that are still running will be killed by raising GreenletExit
        in them, and all timers will be stopped (so that they are not
        retriggered - timer calls that are in progress will not be
        interrupted). This method will **not** block until all threads have
        actually exited, nor that all in-progress timer calls have completed.
        To guarantee that all threads have exited, call :func:`wait`. If all
        threads complete before the timeout expires, timers will be left
        running; there is no way to then stop those timers, so for consistent
        behaviour :func`stop_timers` should be called before calling this
        method.

        :param throw_args: the `exc_info` data to raise from
                           :func:`Thread.wait` for any of the unstarted
                           threads. (Though note that :func:`ThreadGroup.wait`
                           suppresses exceptions.)
        :param timeout: time to wait for running threads to complete before
                        calling stop(). If not supplied, threads that are
                        already running continue to completion.
        :param wait_time: length of time in seconds to sleep between checks of
                          whether any threads are still alive. (Default 1s.)
        """
        self._perform_action_on_threads(
            lambda x: x.cancel(*throw_args),
            lambda x: LOG.exception('Error canceling thread.'))

        timeout = kwargs.get('timeout', None)
        if timeout is None:
            return
        wait_time = kwargs.get('wait_time', 1)
        watch = timeutils.StopWatch(duration=timeout)
        watch.start()
        while self._any_threads_alive():
            if not watch.expired():
                eventlet.sleep(wait_time)
                continue
            LOG.debug("Cancel timeout reached, stopping threads.")
            self.stop()
