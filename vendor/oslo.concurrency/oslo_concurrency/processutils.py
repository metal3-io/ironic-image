# Copyright 2011 OpenStack Foundation.
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

"""
System-level utilities and helper functions.
"""

import functools
import logging
import multiprocessing
import os
import random
import shlex
import signal
import sys
import time

import enum
from oslo_utils import encodeutils
from oslo_utils import importutils
from oslo_utils import strutils
from oslo_utils import timeutils
import six

from oslo_concurrency._i18n import _


# NOTE(bnemec): eventlet doesn't monkey patch subprocess, so we need to
# determine the proper subprocess module to use ourselves.  I'm using the
# time module as the check because that's a monkey patched module we use
# in combination with subprocess below, so they need to match.
eventlet = importutils.try_import('eventlet')
eventlet_patched = eventlet and eventlet.patcher.is_monkey_patched(time)
if eventlet_patched:
    if os.name == 'nt':
        # subprocess.Popen.communicate will spawn two threads consuming
        # stdout/stderr when passing data through stdin. We need to make
        # sure that *native* threads will be used as pipes are blocking
        # on Windows.
        # Recent eventlet versions actually do patch subprocess.
        subprocess = eventlet.patcher.original('subprocess')
        subprocess.threading = eventlet.patcher.original('threading')
    else:
        from eventlet.green import subprocess

    from eventlet import tpool
else:
    import subprocess


LOG = logging.getLogger(__name__)


class InvalidArgumentError(Exception):
    def __init__(self, message=None):
        super(InvalidArgumentError, self).__init__(message)


class UnknownArgumentError(Exception):
    def __init__(self, message=None):
        super(UnknownArgumentError, self).__init__(message)


class ProcessExecutionError(Exception):
    def __init__(self, stdout=None, stderr=None, exit_code=None, cmd=None,
                 description=None):
        super(ProcessExecutionError, self).__init__(
            stdout, stderr, exit_code, cmd, description)
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout
        self.cmd = cmd
        self.description = description

    def __str__(self):
        description = self.description
        if description is None:
            description = _("Unexpected error while running command.")

        exit_code = self.exit_code
        if exit_code is None:
            exit_code = '-'

        message = _('%(description)s\n'
                    'Command: %(cmd)s\n'
                    'Exit code: %(exit_code)s\n'
                    'Stdout: %(stdout)r\n'
                    'Stderr: %(stderr)r') % {'description': description,
                                             'cmd': self.cmd,
                                             'exit_code': exit_code,
                                             'stdout': self.stdout,
                                             'stderr': self.stderr}
        return message


class NoRootWrapSpecified(Exception):
    def __init__(self, message=None):
        super(NoRootWrapSpecified, self).__init__(message)


def _subprocess_setup(on_preexec_fn):
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    if on_preexec_fn:
        on_preexec_fn()


@enum.unique
class LogErrors(enum.IntEnum):
    """Enumerations that affect if stdout and stderr are logged on error.

    .. versionadded:: 2.7
    """

    #: No logging on errors.
    DEFAULT = 0

    #: Log an error on **each** occurence of an error.
    ALL = 1

    #: Log an error on the last attempt that errored **only**.
    FINAL = 2


# Retain these aliases for a number of releases...
LOG_ALL_ERRORS = LogErrors.ALL
LOG_FINAL_ERROR = LogErrors.FINAL
LOG_DEFAULT_ERROR = LogErrors.DEFAULT


class ProcessLimits(object):
    """Resource limits on a process.

    Attributes:

    * address_space: Address space limit in bytes
    * core_file_size: Core file size limit in bytes
    * cpu_time: CPU time limit in seconds
    * data_size: Data size limit in bytes
    * file_size: File size limit in bytes
    * memory_locked: Locked memory limit in bytes
    * number_files: Maximum number of open files
    * number_processes: Maximum number of processes
    * resident_set_size: Maximum Resident Set Size (RSS) in bytes
    * stack_size: Stack size limit in bytes

    This object can be used for the *prlimit* parameter of :func:`execute`.
    """

    _LIMITS = {
        "address_space": "--as",
        "core_file_size": "--core",
        "cpu_time": "--cpu",
        "data_size": "--data",
        "file_size": "--fsize",
        "memory_locked": "--memlock",
        "number_files": "--nofile",
        "number_processes": "--nproc",
        "resident_set_size": "--rss",
        "stack_size": "--stack",
    }

    def __init__(self, **kw):
        for limit in self._LIMITS.keys():
            setattr(self, limit, kw.pop(limit, None))

        if kw:
            raise ValueError("invalid limits: %s"
                             % ', '.join(sorted(kw.keys())))

    def prlimit_args(self):
        """Create a list of arguments for the prlimit command line."""
        args = []
        for limit in self._LIMITS.keys():
            val = getattr(self, limit)
            if val is not None:
                args.append("%s=%s" % (self._LIMITS[limit], val))
        return args


def execute(*cmd, **kwargs):
    """Helper method to shell out and execute a command through subprocess.

    Allows optional retry.

    :param cmd:             Passed to subprocess.Popen.
    :type cmd:              string
    :param cwd:             Set the current working directory
    :type cwd:              string
    :param process_input:   Send to opened process.
    :type process_input:    string or bytes
    :param env_variables:   Environment variables and their values that
                            will be set for the process.
    :type env_variables:    dict
    :param check_exit_code: Single bool, int, or list of allowed exit
                            codes.  Defaults to [0].  Raise
                            :class:`ProcessExecutionError` unless
                            program exits with one of these code.
    :type check_exit_code:  boolean, int, or [int]
    :param delay_on_retry:  True | False. Defaults to True. If set to True,
                            wait a short amount of time before retrying.
    :type delay_on_retry:   boolean
    :param attempts:        How many times to retry cmd.
    :type attempts:         int
    :param run_as_root:     True | False. Defaults to False. If set to True,
                            the command is prefixed by the command specified
                            in the root_helper kwarg.
    :type run_as_root:      boolean
    :param root_helper:     command to prefix to commands called with
                            run_as_root=True
    :type root_helper:      string
    :param shell:           whether or not there should be a shell used to
                            execute this command. Defaults to false.
    :type shell:            boolean
    :param loglevel:        log level for execute commands.
    :type loglevel:         int.  (Should be logging.DEBUG or logging.INFO)
    :param log_errors:      Should stdout and stderr be logged on error?
                            Possible values are
                            :py:attr:`~.LogErrors.DEFAULT`,
                            :py:attr:`~.LogErrors.FINAL`, or
                            :py:attr:`~.LogErrors.ALL`. Note that the
                            values :py:attr:`~.LogErrors.FINAL` and
                            :py:attr:`~.LogErrors.ALL`
                            are **only** relevant when multiple attempts of
                            command execution are requested using the
                            ``attempts`` parameter.
    :type log_errors:       :py:class:`~.LogErrors`
    :param binary:          On Python 3, return stdout and stderr as bytes if
                            binary is True, as Unicode otherwise.
    :type binary:           boolean
    :param on_execute:      This function will be called upon process creation
                            with the object as a argument.  The Purpose of this
                            is to allow the caller of `processutils.execute` to
                            track process creation asynchronously.
    :type on_execute:       function(:class:`subprocess.Popen`)
    :param on_completion:   This function will be called upon process
                            completion with the object as a argument.  The
                            Purpose of this is to allow the caller of
                            `processutils.execute` to track process completion
                            asynchronously.
    :type on_completion:    function(:class:`subprocess.Popen`)
    :param preexec_fn:      This function will be called
                            in the child process just before the child
                            is executed. WARNING: On windows, we silently
                            drop this preexec_fn as it is not supported by
                            subprocess.Popen on windows (throws a
                            ValueError)
    :type preexec_fn:       function()
    :param prlimit:         Set resource limits on the child process. See
                            below for a detailed description.
    :type prlimit:          :class:`ProcessLimits`
    :param python_exec:     The python executable to use for enforcing
                            prlimits. If this is not set it will default to use
                            sys.executable.
    :type python_exec:      string
    :returns:               (stdout, stderr) from process execution
    :raises:                :class:`UnknownArgumentError` on
                            receiving unknown arguments
    :raises:                :class:`ProcessExecutionError`
    :raises:                :class:`OSError`

    The *prlimit* parameter can be used to set resource limits on the child
    process.  If this parameter is used, the child process will be spawned by a
    wrapper process which will set limits before spawning the command.

    .. versionchanged:: 3.17
       *process_input* can now be either bytes or string on python3.

    .. versionchanged:: 3.4
       Added *prlimit* optional parameter.

    .. versionchanged:: 1.5
       Added *cwd* optional parameter.

    .. versionchanged:: 1.9
       Added *binary* optional parameter. On Python 3, *stdout* and *stderr*
       are now returned as Unicode strings by default, or bytes if *binary* is
       true.

    .. versionchanged:: 2.1
       Added *on_execute* and *on_completion* optional parameters.

    .. versionchanged:: 2.3
       Added *preexec_fn* optional parameter.
    """

    cwd = kwargs.pop('cwd', None)
    process_input = kwargs.pop('process_input', None)
    if process_input is not None:
        process_input = encodeutils.to_utf8(process_input)
    env_variables = kwargs.pop('env_variables', None)
    check_exit_code = kwargs.pop('check_exit_code', [0])
    ignore_exit_code = False
    delay_on_retry = kwargs.pop('delay_on_retry', True)
    attempts = kwargs.pop('attempts', 1)
    run_as_root = kwargs.pop('run_as_root', False)
    root_helper = kwargs.pop('root_helper', '')
    shell = kwargs.pop('shell', False)
    loglevel = kwargs.pop('loglevel', logging.DEBUG)
    log_errors = kwargs.pop('log_errors', None)
    if log_errors is None:
        log_errors = LogErrors.DEFAULT
    binary = kwargs.pop('binary', False)
    on_execute = kwargs.pop('on_execute', None)
    on_completion = kwargs.pop('on_completion', None)
    preexec_fn = kwargs.pop('preexec_fn', None)
    prlimit = kwargs.pop('prlimit', None)
    python_exec = kwargs.pop('python_exec', sys.executable)

    if isinstance(check_exit_code, bool):
        ignore_exit_code = not check_exit_code
        check_exit_code = [0]
    elif isinstance(check_exit_code, int):
        check_exit_code = [check_exit_code]

    if kwargs:
        raise UnknownArgumentError(_('Got unknown keyword args: %r') % kwargs)

    if isinstance(log_errors, six.integer_types):
        log_errors = LogErrors(log_errors)
    if not isinstance(log_errors, LogErrors):
        raise InvalidArgumentError(_('Got invalid arg log_errors: %r') %
                                   log_errors)

    if run_as_root and hasattr(os, 'geteuid') and os.geteuid() != 0:
        if not root_helper:
            raise NoRootWrapSpecified(
                message=_('Command requested root, but did not '
                          'specify a root helper.'))
        if shell:
            # root helper has to be injected into the command string
            cmd = [' '.join((root_helper, cmd[0]))] + list(cmd[1:])
        else:
            # root helper has to be tokenized into argument list
            cmd = shlex.split(root_helper) + list(cmd)

    cmd = [str(c) for c in cmd]

    if prlimit:
        if os.name == 'nt':
            LOG.log(loglevel,
                    _('Process resource limits are ignored as '
                      'this feature is not supported on Windows.'))
        else:
            args = [python_exec, '-m', 'oslo_concurrency.prlimit']
            args.extend(prlimit.prlimit_args())
            args.append('--')
            args.extend(cmd)
            cmd = args

    sanitized_cmd = strutils.mask_password(' '.join(cmd))

    watch = timeutils.StopWatch()
    while attempts > 0:
        attempts -= 1
        watch.restart()

        try:
            LOG.log(loglevel, _('Running cmd (subprocess): %s'), sanitized_cmd)
            _PIPE = subprocess.PIPE  # pylint: disable=E1101

            if os.name == 'nt':
                on_preexec_fn = None
                close_fds = False
            else:
                on_preexec_fn = functools.partial(_subprocess_setup,
                                                  preexec_fn)
                close_fds = True

            obj = subprocess.Popen(cmd,
                                   stdin=_PIPE,
                                   stdout=_PIPE,
                                   stderr=_PIPE,
                                   close_fds=close_fds,
                                   preexec_fn=on_preexec_fn,
                                   shell=shell,  # nosec:B604
                                   cwd=cwd,
                                   env=env_variables)

            if on_execute:
                on_execute(obj)

            try:
                # eventlet.green.subprocess is not really greenthread friendly
                # on Windows. In order to avoid blocking other greenthreads,
                # we have to wrap this call using tpool.
                if eventlet_patched and os.name == 'nt':
                    result = tpool.execute(obj.communicate,
                                           process_input)
                else:
                    result = obj.communicate(process_input)

                obj.stdin.close()  # pylint: disable=E1101
                _returncode = obj.returncode  # pylint: disable=E1101
                LOG.log(loglevel, 'CMD "%s" returned: %s in %0.3fs',
                        sanitized_cmd, _returncode, watch.elapsed())
            finally:
                if on_completion:
                    on_completion(obj)

            if not ignore_exit_code and _returncode not in check_exit_code:
                (stdout, stderr) = result
                if six.PY3:
                    stdout = os.fsdecode(stdout)
                    stderr = os.fsdecode(stderr)
                sanitized_stdout = strutils.mask_password(stdout)
                sanitized_stderr = strutils.mask_password(stderr)
                raise ProcessExecutionError(exit_code=_returncode,
                                            stdout=sanitized_stdout,
                                            stderr=sanitized_stderr,
                                            cmd=sanitized_cmd)
            if six.PY3 and not binary and result is not None:
                (stdout, stderr) = result
                # Decode from the locale using using the surrogateescape error
                # handler (decoding cannot fail)
                stdout = os.fsdecode(stdout)
                stderr = os.fsdecode(stderr)
                return (stdout, stderr)
            else:
                return result

        except (ProcessExecutionError, OSError) as err:
            # if we want to always log the errors or if this is
            # the final attempt that failed and we want to log that.
            if log_errors == LOG_ALL_ERRORS or (
                    log_errors == LOG_FINAL_ERROR and not attempts):
                if isinstance(err, ProcessExecutionError):
                    format = _('%(desc)r\ncommand: %(cmd)r\n'
                               'exit code: %(code)r\nstdout: %(stdout)r\n'
                               'stderr: %(stderr)r')
                    LOG.log(loglevel, format, {"desc": err.description,
                                               "cmd": err.cmd,
                                               "code": err.exit_code,
                                               "stdout": err.stdout,
                                               "stderr": err.stderr})
                else:
                    format = _('Got an OSError\ncommand: %(cmd)r\n'
                               'errno: %(errno)r')
                    LOG.log(loglevel, format, {"cmd": sanitized_cmd,
                                               "errno": err.errno})

            if not attempts:
                LOG.log(loglevel, _('%r failed. Not Retrying.'),
                        sanitized_cmd)
                raise
            else:
                LOG.log(loglevel, _('%r failed. Retrying.'),
                        sanitized_cmd)
                if delay_on_retry:
                    time.sleep(random.randint(20, 200) / 100.0)
        finally:
            # NOTE(termie): this appears to be necessary to let the subprocess
            #               call clean something up in between calls, without
            #               it two execute calls in a row hangs the second one
            # NOTE(bnemec): termie's comment above is probably specific to the
            #               eventlet subprocess module, but since we still
            #               have to support that we're leaving the sleep.  It
            #               won't hurt anything in the stdlib case anyway.
            time.sleep(0)


def trycmd(*args, **kwargs):
    """A wrapper around execute() to more easily handle warnings and errors.

    Returns an (out, err) tuple of strings containing the output of
    the command's stdout and stderr.  If 'err' is not empty then the
    command can be considered to have failed.

    :param discard_warnings:  True | False. Defaults to False. If set to True,
                              then for succeeding commands, stderr is cleared
    :type discard_warnings:   boolean
    :returns:                 (out, err) from process execution

    """
    discard_warnings = kwargs.pop('discard_warnings', False)

    try:
        out, err = execute(*args, **kwargs)
        failed = False
    except ProcessExecutionError as exn:
        out, err = '', six.text_type(exn)
        failed = True

    if not failed and discard_warnings and err:
        # Handle commands that output to stderr but otherwise succeed
        err = ''

    return out, err


def ssh_execute(ssh, cmd, process_input=None,
                addl_env=None, check_exit_code=True,
                binary=False, timeout=None,
                sanitize_stdout=True):
    """Run a command through SSH.

    :param ssh:             An SSH Connection object.
    :param cmd:             The command string to run.
    :param check_exit_code: If an exception should be raised for non-zero
                            exit.
    :param timeout:         Max time in secs to wait for command execution.
    :param sanitize_stdout: Defaults to True. If set to True, stdout is
                            sanitized i.e. any sensitive information like
                            password in command output will be masked.
    :returns:               (stdout, stderr) from command execution through
                            SSH.

    .. versionchanged:: 1.9
       Added *binary* optional parameter.
    """
    sanitized_cmd = strutils.mask_password(cmd)
    LOG.debug('Running cmd (SSH): %s', sanitized_cmd)
    if addl_env:
        raise InvalidArgumentError(_('Environment not supported over SSH'))

    if process_input:
        # This is (probably) fixable if we need it...
        raise InvalidArgumentError(_('process_input not supported over SSH'))

    stdin_stream, stdout_stream, stderr_stream = ssh.exec_command(
        cmd, timeout=timeout)
    channel = stdout_stream.channel

    # NOTE(justinsb): This seems suspicious...
    # ...other SSH clients have buffering issues with this approach
    stdout = stdout_stream.read()
    stderr = stderr_stream.read()

    stdin_stream.close()

    exit_status = channel.recv_exit_status()

    if six.PY3:
        # Decode from the locale using using the surrogateescape error handler
        # (decoding cannot fail). Decode even if binary is True because
        # mask_password() requires Unicode on Python 3
        stdout = os.fsdecode(stdout)
        stderr = os.fsdecode(stderr)

    if sanitize_stdout:
        stdout = strutils.mask_password(stdout)

    stderr = strutils.mask_password(stderr)

    # exit_status == -1 if no exit code was returned
    if exit_status != -1:
        LOG.debug('Result was %s' % exit_status)
        if check_exit_code and exit_status != 0:
            # In case of errors in command run, due to poor implementation of
            # command executable program, there might be chance that it leaks
            # sensitive information like password to stdout. In such cases
            # stdout needs to be sanitized even though sanitize_stdout=False.
            stdout = strutils.mask_password(stdout)
            raise ProcessExecutionError(exit_code=exit_status,
                                        stdout=stdout,
                                        stderr=stderr,
                                        cmd=sanitized_cmd)

    if binary:
        if six.PY2:
            # On Python 2, stdout is a bytes string if mask_password() failed
            # to decode it, or an Unicode string otherwise. Encode to the
            # default encoding (ASCII) because mask_password() decodes from
            # the same encoding.
            if isinstance(stdout, six.text_type):
                stdout = stdout.encode()
            if isinstance(stderr, six.text_type):
                stderr = stderr.encode()
        else:
            # fsencode() is the reverse operation of fsdecode()
            stdout = os.fsencode(stdout)
            stderr = os.fsencode(stderr)

    return (stdout, stderr)


def get_worker_count():
    """Utility to get the default worker count.

    :returns: The number of CPUs if that can be determined, else a default
              worker count of 1 is returned.
    """
    try:
        return multiprocessing.cpu_count()
    except NotImplementedError:
        return 1
