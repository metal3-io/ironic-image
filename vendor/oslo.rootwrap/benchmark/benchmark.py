# Copyright (c) 2014 Mirantis Inc.
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

import atexit
import math
import os
import six
import subprocess
import sys
import timeit

from oslo_rootwrap import client

config_path = "rootwrap.conf"
num_iterations = 100


def run_plain(cmd):
    obj = subprocess.Popen(cmd,
                           stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    out, err = obj.communicate()
    if six.PY3:
        out = os.fsdecode(out)
        err = os.fsdecode(err)
    return obj.returncode, out, err


def run_sudo(cmd):
    return run_plain(["sudo"] + cmd)


def run_rootwrap(cmd):
    return run_plain([
        "sudo", sys.executable, "-c",
        "from oslo_rootwrap import cmd; cmd.main()", config_path] + cmd)


run_daemon = client.Client([
    "sudo", sys.executable, "-c",
    "from oslo_rootwrap import cmd; cmd.daemon()", config_path]).execute


def run_one(runner, cmd):
    def __inner():
        code, out, err = runner(cmd)
        assert err == "", "Stderr not empty:\n" + err
        assert code == 0, "Command failed"
    return __inner

runners = [
    ("{0}", run_plain),
    ("sudo {0}", run_sudo),
    ("sudo rootwrap conf {0}", run_rootwrap),
    ("daemon.run('{0}')", run_daemon),
]


def get_time_string(sec):
    if sec > 0.9:
        return "{0:7.3f}s ".format(sec)
    elif sec > 0.0009:
        return "{0:7.3f}ms".format(sec * 1000.0)
    else:
        return "{0:7.3f}us".format(sec * 1000000.0)


def run_bench(cmd, runners):
    strcmd = ' '.join(cmd)
    max_name_len = max(len(name) for name, _ in runners) + len(strcmd) - 3
    print("Running '{0}':".format(strcmd))
    print("{0:^{1}} :".format("method", max_name_len),
          "".join(map("{0:^10}".format, ["min", "avg", "max", "dev"])))
    for name, runner in runners:
        results = timeit.repeat(run_one(runner, cmd), repeat=num_iterations,
                                number=1)
        avg = sum(results) / num_iterations
        min_ = min(results)
        max_ = max(results)
        dev = math.sqrt(sum((r - avg) ** 2 for r in results) / num_iterations)
        print("{0:>{1}} :".format(name.format(strcmd), max_name_len),
              " ".join(map(get_time_string, [min_, avg, max_, dev])))


def main():
    os.chdir(os.path.dirname(__file__))
    code, _, _ = run_sudo(["-vn"])
    if code:
        print("We need you to authorize with sudo to run this benchmark")
        run_sudo(["-v"])

    run_bench(["ip", "a"], runners)
    run_sudo(["ip", "netns", "add", "bench_ns"])
    atexit.register(run_sudo, ["ip", "netns", "delete", "bench_ns"])
    run_bench('ip netns exec bench_ns ip a'.split(), runners[1:])

if __name__ == "__main__":
    main()
