# Copyright (c) 2012 OpenStack Foundation.
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
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

from __future__ import print_function

import errno
import gc
import logging
import os
import pprint
import sys
import tempfile
import traceback

import eventlet.backdoor
import greenlet
import yappi

from eventlet.green import socket
from oslo_service._i18n import _
from oslo_service import _options


LOG = logging.getLogger(__name__)


class EventletBackdoorConfigValueError(Exception):
    def __init__(self, port_range, help_msg, ex):
        msg = (_('Invalid backdoor_port configuration %(range)s: %(ex)s. '
               '%(help)s') %
               {'range': port_range, 'ex': ex, 'help': help_msg})
        super(EventletBackdoorConfigValueError, self).__init__(msg)
        self.port_range = port_range


def _dont_use_this():
    print("Don't use this, just disconnect instead")


def _dump_frame(f, frame_chapter):
    co = f.f_code
    print(" %s Frame: %s" % (frame_chapter, co.co_name))
    print("     File: %s" % (co.co_filename))
    print("     Captured at line number: %s" % (f.f_lineno))
    co_locals = set(co.co_varnames)
    if len(co_locals):
        not_set = co_locals.copy()
        set_locals = {}
        for var_name in f.f_locals.keys():
            if var_name in co_locals:
                set_locals[var_name] = f.f_locals[var_name]
                not_set.discard(var_name)
        if set_locals:
            print("     %s set local variables:" % (len(set_locals)))
            for var_name in sorted(set_locals.keys()):
                print("       %s => %r" % (var_name, f.f_locals[var_name]))
        else:
            print("     0 set local variables.")
        if not_set:
            print("     %s not set local variables:" % (len(not_set)))
            for var_name in sorted(not_set):
                print("       %s" % (var_name))
        else:
            print("     0 not set local variables.")
    else:
        print("     0 Local variables.")


def _detailed_dump_frames(f, thread_index):
    i = 0
    while f is not None:
        _dump_frame(f, "%s.%s" % (thread_index, i + 1))
        f = f.f_back
        i += 1


def _find_objects(t):
    return [o for o in gc.get_objects() if isinstance(o, t)]


def _capture_profile(fname=''):
    if not fname:
        yappi.set_clock_type('cpu')
        # We need to set context to greenlet to profile greenlets
        # https://bitbucket.org/sumerc/yappi/pull-requests/3
        yappi.set_context_id_callback(
            lambda: id(greenlet.getcurrent()))
        yappi.set_context_name_callback(
            lambda: greenlet.getcurrent().__class__.__name__)
        yappi.start()
    else:
        yappi.stop()
        stats = yappi.get_func_stats()
        # User should provide filename. This file with a suffix .prof
        # will be created in temp directory.
        try:
            stats_file = os.path.join(tempfile.gettempdir(), fname + '.prof')
            stats.save(stats_file, "pstat")
        except Exception as e:
            print("Error while saving the trace stats ", str(e))
        finally:
            yappi.clear_stats()


def _print_greenthreads(simple=True):
    for i, gt in enumerate(_find_objects(greenlet.greenlet)):
        print(i, gt)
        if simple:
            traceback.print_stack(gt.gr_frame)
        else:
            _detailed_dump_frames(gt.gr_frame, i)
        print()


def _print_nativethreads():
    for threadId, stack in sys._current_frames().items():
        print(threadId)
        traceback.print_stack(stack)
        print()


def _parse_port_range(port_range):
    if ':' not in port_range:
        start, end = port_range, port_range
    else:
        start, end = port_range.split(':', 1)
    try:
        start, end = int(start), int(end)
        if end < start:
            raise ValueError
        return start, end
    except ValueError as ex:
        raise EventletBackdoorConfigValueError(
            port_range, ex, _options.help_for_backdoor_port)


def _listen_func(host, port):
    # eventlet is setting SO_REUSEPORT by default from v0.20.
    # But we can configure it by passing reuse_port argument
    # from v0.22
    try:
        return eventlet.listen((host, port), reuse_port=False)
    except TypeError:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, port))
        sock.listen(50)
        return sock


def _listen(host, start_port, end_port):
    try_port = start_port
    while True:
        try:
            return _listen_func(host, try_port)
        except socket.error as exc:
            if (exc.errno != errno.EADDRINUSE or
               try_port >= end_port):
                raise
            try_port += 1


def _try_open_unix_domain_socket(socket_path):
    try:
        return eventlet.listen(socket_path, socket.AF_UNIX)
    except socket.error as e:
        if e.errno != errno.EADDRINUSE:
            # NOTE(harlowja): Some other non-address in use error
            # occurred, since we aren't handling those, re-raise
            # and give up...
            raise
        else:
            # Attempt to remove the file before opening it again.
            try:
                os.unlink(socket_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    # NOTE(harlowja): File existed, but we couldn't
                    # delete it, give up...
                    raise
            return eventlet.listen(socket_path, socket.AF_UNIX)


def _initialize_if_enabled(conf):
    conf.register_opts(_options.eventlet_backdoor_opts)
    backdoor_locals = {
        'exit': _dont_use_this,      # So we don't exit the entire process
        'quit': _dont_use_this,      # So we don't exit the entire process
        'fo': _find_objects,
        'pgt': _print_greenthreads,
        'pnt': _print_nativethreads,
        'prof': _capture_profile,
    }

    if conf.backdoor_port is None and conf.backdoor_socket is None:
        return None

    if conf.backdoor_socket is None:
        start_port, end_port = _parse_port_range(str(conf.backdoor_port))
        sock = _listen('localhost', start_port, end_port)
        # In the case of backdoor port being zero, a port number is assigned by
        # listen().  In any case, pull the port number out here.
        where_running = sock.getsockname()[1]
    else:
        try:
            backdoor_socket_path = conf.backdoor_socket.format(pid=os.getpid())
        except (KeyError, IndexError, ValueError) as e:
            backdoor_socket_path = conf.backdoor_socket
            LOG.warning("Could not apply format string to eventlet "
                        "backdoor socket path ({}) - continuing with "
                        "unformatted path"
                        "".format(e))
        sock = _try_open_unix_domain_socket(backdoor_socket_path)
        where_running = backdoor_socket_path

    # NOTE(johannes): The standard sys.displayhook will print the value of
    # the last expression and set it to __builtin__._, which overwrites
    # the __builtin__._ that gettext sets. Let's switch to using pprint
    # since it won't interact poorly with gettext, and it's easier to
    # read the output too.
    def displayhook(val):
        if val is not None:
            pprint.pprint(val)
    sys.displayhook = displayhook

    LOG.info(
        'Eventlet backdoor listening on %(where_running)s for'
        ' process %(pid)d',
        {'where_running': where_running, 'pid': os.getpid()}
    )
    thread = eventlet.spawn(eventlet.backdoor.backdoor_server, sock,
                            locals=backdoor_locals)
    return (where_running, thread)


def initialize_if_enabled(conf):
    where_running_thread = _initialize_if_enabled(conf)
    if not where_running_thread:
        return None
    else:
        where_running, _thread = where_running_thread
        return where_running


def _main():
    import eventlet
    eventlet.monkey_patch(all=True)

    from oslo_config import cfg

    logging.basicConfig(level=logging.DEBUG)

    conf = cfg.ConfigOpts()
    conf.register_cli_opts(_options.eventlet_backdoor_opts)
    conf(sys.argv[1:])

    where_running_thread = _initialize_if_enabled(conf)
    if not where_running_thread:
        raise RuntimeError(_("Did not create backdoor at requested location"))
    else:
        _where_running, thread = where_running_thread
        thread.wait()


if __name__ == '__main__':
    # simple CLI for testing
    _main()
