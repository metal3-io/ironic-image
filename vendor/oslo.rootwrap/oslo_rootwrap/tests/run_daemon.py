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

import logging
import sys
import threading

from oslo_rootwrap import cmd
from oslo_rootwrap import subprocess


def forward_stream(fr, to):
    while True:
        line = fr.readline()
        if not line:
            break
        to.write(line)


def forwarding_popen(f, old_popen=subprocess.Popen):
    def popen(*args, **kwargs):
        p = old_popen(*args, **kwargs)
        t = threading.Thread(target=forward_stream, args=(p.stderr, f))
        t.daemon = True
        t.start()
        return p
    return popen


class nonclosing(object):
    def __init__(self, f):
        self._f = f

    def __getattr__(self, name):
        return getattr(self._f, name)

    def close(self):
        pass

log_format = ("%(asctime)s | [%(process)5s]+%(levelname)5s | "
              "%(message)s")
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    sys.stderr = nonclosing(sys.stderr)
    cmd.daemon()
