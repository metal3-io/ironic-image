# Copyright 2016 Red Hat.
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

import argparse
import os
import resource
import sys

USAGE_PROGRAM = ('%s -m oslo_concurrency.prlimit'
                 % os.path.basename(sys.executable))

RESOURCES = (
    # argparse argument => resource
    ('as', resource.RLIMIT_AS),
    ('core', resource.RLIMIT_CORE),
    ('cpu', resource.RLIMIT_CPU),
    ('data', resource.RLIMIT_DATA),
    ('fsize', resource.RLIMIT_FSIZE),
    ('memlock', resource.RLIMIT_MEMLOCK),
    ('nofile', resource.RLIMIT_NOFILE),
    ('nproc', resource.RLIMIT_NPROC),
    ('rss', resource.RLIMIT_RSS),
    ('stack', resource.RLIMIT_STACK),
)


def parse_args():
    parser = argparse.ArgumentParser(description='prlimit', prog=USAGE_PROGRAM)
    parser.add_argument('--as', type=int,
                        help='Address space limit in bytes')
    parser.add_argument('--core', type=int,
                        help='Core file size limit in bytes')
    parser.add_argument('--cpu', type=int,
                        help='CPU time limit in seconds')
    parser.add_argument('--data', type=int,
                        help='Data size limit in bytes')
    parser.add_argument('--fsize', type=int,
                        help='File size limit in bytes')
    parser.add_argument('--memlock', type=int,
                        help='Locked memory limit in bytes')
    parser.add_argument('--nofile', type=int,
                        help='Maximum number of open files')
    parser.add_argument('--nproc', type=int,
                        help='Maximum number of processes')
    parser.add_argument('--rss', type=int,
                        help='Maximum Resident Set Size (RSS) in bytes')
    parser.add_argument('--stack', type=int,
                        help='Stack size limit in bytes')
    parser.add_argument('program',
                        help='Program (absolute path)')
    parser.add_argument('program_args', metavar="arg", nargs='...',
                        help='Program parameters')

    args = parser.parse_args()
    return args


def main():
    args = parse_args()

    program = args.program
    if not os.path.isabs(program):
        # program uses a relative path: try to find the absolute path
        # to the executable
        if sys.version_info >= (3, 3):
            import shutil
            program_abs = shutil.which(program)
        else:
            import distutils.spawn
            program_abs = distutils.spawn.find_executable(program)
        if program_abs:
            program = program_abs

    for arg_name, rlimit in RESOURCES:
        value = getattr(args, arg_name)
        if value is None:
            continue
        try:
            resource.setrlimit(rlimit, (value, value))
        except ValueError as exc:
            print("%s: failed to set the %s resource limit: %s"
                  % (USAGE_PROGRAM, arg_name.upper(), exc),
                  file=sys.stderr)
            sys.exit(1)

    try:
        os.execv(program, [program] + args.program_args)
    except Exception as exc:
        print("%s: failed to execute %s: %s"
              % (USAGE_PROGRAM, program, exc),
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
