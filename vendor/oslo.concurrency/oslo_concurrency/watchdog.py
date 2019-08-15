# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
#
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

"""
Watchdog module.

.. versionadded:: 0.4
"""

import contextlib
import logging
import threading

from oslo_utils import timeutils


@contextlib.contextmanager
def watch(logger, action, level=logging.DEBUG, after=5.0):
    """Log a message if an operation exceeds a time threshold.

    This context manager is expected to be used when you are going to
    do an operation in code which might either deadlock or take an
    extraordinary amount of time, and you'd like to emit a status
    message back to the user that the operation is still ongoing but
    has not completed in an expected amount of time. This is more user
    friendly than logging 'start' and 'end' events and making users
    correlate the events to figure out they ended up in a deadlock.

    :param logger: an object that complies to the logger definition
      (has a .log method).

    :param action: a meaningful string that describes the thing you
      are about to do.

    :param level: the logging level the message should be emitted
      at. Defaults to logging.DEBUG.

    :param after: the duration in seconds before the message is
      emitted. Defaults to 5.0 seconds.

    Example usage::

        FORMAT = '%(asctime)-15s %(message)s'
        logging.basicConfig(format=FORMAT)
        LOG = logging.getLogger('mylogger')

        with watchdog.watch(LOG, "subprocess call", logging.ERROR):
            subprocess.call("sleep 10", shell=True)
            print "done"

    """
    watch = timeutils.StopWatch()
    watch.start()

    def log():
        msg = "%s not completed after %0.3fs" % (action, watch.elapsed())
        logger.log(level, msg)

    timer = threading.Timer(after, log)
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        timer.join()
