# Copyright 2017 Cisco Systems, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common utilities and classes across all unit tests."""

import subprocess

from oslo_concurrency import processutils
from oslo_config import fixture as config_fixture
from oslotest import base as test_base

from ironic_lib import utils


class IronicLibTestCase(test_base.BaseTestCase):
    """Test case base class for all unit tests except callers of utils.execute.

    This test class prevents calls to the utils.execute() /
    processutils.execute() and similar functions.
    """

    # By default block execution of utils.execute() and related functions.
    block_execute = True

    def setUp(self):
        super(IronicLibTestCase, self).setUp()

        # Make sure config overrides do not leak for test to test.
        self.cfg_fixture = self.useFixture(config_fixture.Config())

        # Ban running external processes via 'execute' like functions. If the
        # patched function is called, an exception is raised to warn the
        # tester.
        if self.block_execute:
            # NOTE(jlvillal): Intentionally not using mock as if you mock a
            # mock it causes things to not work correctly. As doing an
            # autospec=True causes strangeness. By using a simple function we
            # can then mock it without issue.
            self.patch(processutils, 'execute', do_not_call)
            self.patch(subprocess, 'call', do_not_call)
            self.patch(subprocess, 'check_call', do_not_call)
            self.patch(subprocess, 'check_output', do_not_call)
            self.patch(utils, 'execute', do_not_call)

            # subprocess.Popen is a class
            self.patch(subprocess, 'Popen', DoNotCallPopen)


def do_not_call(*args, **kwargs):
    """Helper function to raise an exception if it is called"""
    raise Exception(
        "Don't call ironic_lib.utils.execute() / "
        "processutils.execute() or similar functions in tests!")


class DoNotCallPopen(object):
    """Helper class to mimic subprocess.popen()

    It's job is to raise an exception if it is called. We create stub functions
    so mocks that use autospec=True will work.
    """
    def __init__(self, *args, **kwargs):
        do_not_call(*args, **kwargs)

    def communicate(self, input=None):
        pass

    def kill(self):
        pass

    def poll(self):
        pass

    def terminate(self):
        pass

    def wait(self):
        pass
