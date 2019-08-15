# Copyright (c) 2015 OpenStack Foundation.
# All Rights Reserved.

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

import codecs
import os
import os.path
import sys

import fixtures
from oslo_config import fixture as config
from oslotest import base as test_base
from six import moves

from oslo_policy import _checks
from oslo_policy import policy


class PolicyBaseTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(PolicyBaseTestCase, self).setUp()
        self.conf = self.useFixture(config.Config()).conf
        self.config_dir = self.useFixture(fixtures.TempDir()).path
        self.conf(args=['--config-dir', self.config_dir])
        self.enforcer = policy.Enforcer(self.conf)
        self.addCleanup(self.enforcer.clear)

    def get_config_file_fullname(self, filename):
        return os.path.join(self.config_dir, filename.lstrip(os.sep))

    def create_config_file(self, filename, contents):
        """Create a configuration file under the config dir.

        Also creates any intermediate paths needed so the file can be
        in a subdirectory.

        """
        path = self.get_config_file_fullname(filename)
        pardir = os.path.dirname(path)
        if not os.path.exists(pardir):
            os.makedirs(pardir)
        with codecs.open(path, 'w', encoding='utf-8') as f:
            f.write(contents)

    def _capture_stdout(self):
        self.useFixture(fixtures.MonkeyPatch('sys.stdout', moves.StringIO()))
        return sys.stdout


class FakeCheck(_checks.BaseCheck):
    def __init__(self, result=None):
        self.result = result

    def __str__(self):
        return str(self.result)

    def __call__(self, target, creds, enforcer):
        if self.result is not None:
            return self.result
        return (target, creds, enforcer)
