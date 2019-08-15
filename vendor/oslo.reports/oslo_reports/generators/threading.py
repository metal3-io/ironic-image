# Copyright 2013 Red Hat, Inc.
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

"""Provides thread-related generators

This module defines classes for threading-related
generators for generating the models in
:mod:`oslo_reports.models.threading`.
"""

from __future__ import absolute_import

import gc
import sys
import threading

from oslo_reports.models import threading as tm
from oslo_reports.models import with_default_views as mwdv
from oslo_reports.views.text import generic as text_views


def _find_objects(t):
    """Find Objects in the GC State

    This horribly hackish method locates objects of a
    given class in the current python instance's garbage
    collection state.  In case you couldn't tell, this is
    horribly hackish, but is necessary for locating all
    green threads, since they don't keep track of themselves
    like normal threads do in python.

    :param class t: the class of object to locate
    :rtype: list
    :returns: a list of objects of the given type
    """

    return [o for o in gc.get_objects() if isinstance(o, t)]


class ThreadReportGenerator(object):
    """A Thread Data Generator

    This generator returns a collection of
    :class:`oslo_reports.models.threading.ThreadModel`
    objects by introspecting the current python state using
    :func:`sys._current_frames()` .  Its constructor may optionally
    be passed a frame object.  This frame object will be interpreted
    as the actual stack trace for the current thread, and, come generation
    time, will be used to replace the stack trace of the thread in which
    this code is running.
    """

    def __init__(self, curr_thread_traceback=None):
        self.traceback = curr_thread_traceback

    def __call__(self):
        threadModels = dict(
            (thread_id, tm.ThreadModel(thread_id, stack))
            for thread_id, stack in sys._current_frames().items()
        )

        if self.traceback is not None:
            curr_thread_id = threading.current_thread().ident
            threadModels[curr_thread_id] = tm.ThreadModel(curr_thread_id,
                                                          self.traceback)

        return mwdv.ModelWithDefaultViews(threadModels,
                                          text_view=text_views.MultiView())


class GreenThreadReportGenerator(object):
    """A Green Thread Data Generator

    This generator returns a collection of
    :class:`oslo_reports.models.threading.GreenThreadModel`
    objects by introspecting the current python garbage collection
    state, and sifting through for :class:`greenlet.greenlet` objects.

    .. seealso::

        Function :func:`_find_objects`
    """

    def __call__(self):
        import greenlet

        threadModels = [
            tm.GreenThreadModel(gr.gr_frame)
            for gr in _find_objects(greenlet.greenlet)
        ]

        return mwdv.ModelWithDefaultViews(threadModels,
                                          text_view=text_views.MultiView())
