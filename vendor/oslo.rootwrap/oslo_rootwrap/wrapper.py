# Copyright (c) 2011 OpenStack Foundation.
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

import logging
import logging.handlers
import os
import signal
import sys

import six
from six import moves

from oslo_rootwrap import filters
from oslo_rootwrap import subprocess

if sys.platform != 'win32':
    import pwd


class NoFilterMatched(Exception):
    """This exception is raised when no filter matched."""
    pass


class FilterMatchNotExecutable(Exception):
    """Raised when a filter matched but no executable was found."""
    def __init__(self, match=None, **kwargs):
        self.match = match


class RootwrapConfig(object):

    def __init__(self, config):
        # filters_path
        self.filters_path = config.get("DEFAULT", "filters_path").split(",")

        # exec_dirs
        if config.has_option("DEFAULT", "exec_dirs"):
            self.exec_dirs = config.get("DEFAULT", "exec_dirs").split(",")
        else:
            self.exec_dirs = []
            # Use system PATH if exec_dirs is not specified
            if "PATH" in os.environ:
                self.exec_dirs = os.environ['PATH'].split(':')

        # syslog_log_facility
        if config.has_option("DEFAULT", "syslog_log_facility"):
            v = config.get("DEFAULT", "syslog_log_facility")
            facility_names = logging.handlers.SysLogHandler.facility_names
            self.syslog_log_facility = getattr(logging.handlers.SysLogHandler,
                                               v, None)
            if self.syslog_log_facility is None and v in facility_names:
                self.syslog_log_facility = facility_names.get(v)
            if self.syslog_log_facility is None:
                raise ValueError('Unexpected syslog_log_facility: %s' % v)
        else:
            default_facility = logging.handlers.SysLogHandler.LOG_SYSLOG
            self.syslog_log_facility = default_facility

        # syslog_log_level
        if config.has_option("DEFAULT", "syslog_log_level"):
            v = config.get("DEFAULT", "syslog_log_level")
            level = v.upper()
            if (hasattr(logging, '_nameToLevel') and
               level in logging._nameToLevel):
                # Workaround a regression of Python 3.4.0 bug fixed in 3.4.2:
                # http://bugs.python.org/issue22386
                self.syslog_log_level = logging._nameToLevel[level]
            else:
                self.syslog_log_level = logging.getLevelName(level)
            if (self.syslog_log_level == "Level %s" % level):
                raise ValueError('Unexpected syslog_log_level: %r' % v)
        else:
            self.syslog_log_level = logging.ERROR

        # use_syslog
        if config.has_option("DEFAULT", "use_syslog"):
            self.use_syslog = config.getboolean("DEFAULT", "use_syslog")
        else:
            self.use_syslog = False

        # daemon_timeout
        if config.has_option("DEFAULT", "daemon_timeout"):
            self.daemon_timeout = int(config.get("DEFAULT", "daemon_timeout"))
        else:
            self.daemon_timeout = 600

        # fd ulimit
        if config.has_option("DEFAULT", "rlimit_nofile"):
            self.rlimit_nofile = int(config.get("DEFAULT", "rlimit_nofile"))
        else:
            self.rlimit_nofile = 1024


def setup_syslog(execname, facility, level):
    try:
        handler = logging.handlers.SysLogHandler(address='/dev/log',
                                                 facility=facility)
    except IOError:
        logging.warning("Unable to setup syslog, maybe /dev/log socket needs "
                        "to be restarted. Ignoring syslog configuration "
                        "options.")
        return

    rootwrap_logger = logging.getLogger()
    rootwrap_logger.setLevel(level)
    handler.setFormatter(logging.Formatter(
                         os.path.basename(execname) + ': %(message)s'))
    rootwrap_logger.addHandler(handler)


def build_filter(class_name, *args):
    """Returns a filter object of class class_name."""
    if not hasattr(filters, class_name):
        logging.warning("Skipping unknown filter class (%s) specified "
                        "in filter definitions" % class_name)
        return None
    filterclass = getattr(filters, class_name)
    return filterclass(*args)


def load_filters(filters_path):
    """Load filters from a list of directories."""
    filterlist = []
    for filterdir in filters_path:
        if not os.path.isdir(filterdir):
            continue
        for filterfile in filter(lambda f: not f.startswith('.'),
                                 os.listdir(filterdir)):
            filterfilepath = os.path.join(filterdir, filterfile)
            if not os.path.isfile(filterfilepath):
                continue
            kwargs = {"strict": False} if six.PY3 else {}
            filterconfig = moves.configparser.RawConfigParser(**kwargs)
            filterconfig.read(filterfilepath)
            for (name, value) in filterconfig.items("Filters"):
                filterdefinition = [s.strip() for s in value.split(',')]
                newfilter = build_filter(*filterdefinition)
                if newfilter is None:
                    continue
                newfilter.name = name
                filterlist.append(newfilter)
    # And always include privsep-helper
    privsep = build_filter("CommandFilter", "privsep-helper", "root")
    privsep.name = "privsep-helper"
    filterlist.append(privsep)
    return filterlist


def match_filter(filter_list, userargs, exec_dirs=None):
    """Checks user command and arguments through command filters.

    Returns the first matching filter.

    Raises NoFilterMatched if no filter matched.
    Raises FilterMatchNotExecutable if no executable was found for the
    best filter match.
    """
    first_not_executable_filter = None
    exec_dirs = exec_dirs or []

    for f in filter_list:
        if f.match(userargs):
            if isinstance(f, filters.ChainingFilter):
                # This command calls exec verify that remaining args
                # matches another filter.
                def non_chain_filter(fltr):
                    return (fltr.run_as == f.run_as and
                            not isinstance(fltr, filters.ChainingFilter))

                leaf_filters = [fltr for fltr in filter_list
                                if non_chain_filter(fltr)]
                args = f.exec_args(userargs)
                if not args:
                    continue
                try:
                    match_filter(leaf_filters, args, exec_dirs=exec_dirs)
                except (NoFilterMatched, FilterMatchNotExecutable):
                    continue

            # Try other filters if executable is absent
            if not f.get_exec(exec_dirs=exec_dirs):
                if not first_not_executable_filter:
                    first_not_executable_filter = f
                continue
            # Otherwise return matching filter for execution
            return f

    if first_not_executable_filter:
        # A filter matched, but no executable was found for it
        raise FilterMatchNotExecutable(match=first_not_executable_filter)

    # No filter matched
    raise NoFilterMatched()


def _getlogin():
    try:
        return os.getlogin()
    except OSError:
        return (os.getenv('USER') or
                os.getenv('USERNAME') or
                os.getenv('LOGNAME'))


def start_subprocess(filter_list, userargs, exec_dirs=[], log=False, **kwargs):
    filtermatch = match_filter(filter_list, userargs, exec_dirs)

    command = filtermatch.get_command(userargs, exec_dirs)
    if log:
        logging.info("(%s > %s) Executing %s (filter match = %s)" % (
            _getlogin(), pwd.getpwuid(os.getuid())[0],
            command, filtermatch.name))

    def preexec():
        # Python installs a SIGPIPE handler by default. This is
        # usually not what non-Python subprocesses expect.
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        filtermatch.preexec()

    obj = subprocess.Popen(command,
                           preexec_fn=preexec,
                           env=filtermatch.get_environment(userargs),
                           **kwargs)
    return obj
