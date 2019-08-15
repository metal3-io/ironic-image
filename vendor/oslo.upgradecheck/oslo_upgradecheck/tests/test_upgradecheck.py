# -*- coding: utf-8 -*-

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
test_upgradecheck
----------------------------------

Tests for `upgradecheck` module.
"""

import os.path
import subprocess
import sys

import mock
from oslo_config import cfg
from oslotest import base

from oslo_upgradecheck import upgradecheck


class TestUpgradeCheckResult(base.BaseTestCase):

    def test_details(self):
        result = upgradecheck.Result(upgradecheck.Code.SUCCESS, 'test details')
        self.assertEqual(0, result.code)
        self.assertEqual('test details', result.details)


class TestCommands(upgradecheck.UpgradeCommands):
    def success(self):
        return upgradecheck.Result(upgradecheck.Code.SUCCESS,
                                   'Always succeeds')

    def warning(self):
        return upgradecheck.Result(upgradecheck.Code.WARNING, 'Always warns')

    def failure(self):
        return upgradecheck.Result(upgradecheck.Code.FAILURE, 'Always fails')

    _upgrade_checks = (('always succeeds', success),
                       ('always warns', warning),
                       ('always fails', failure),
                       )


class SuccessCommands(TestCommands):
    _upgrade_checks = ()


class TestUpgradeCommands(base.BaseTestCase):
    def test_get_details(self):
        result = upgradecheck.Result(upgradecheck.Code.SUCCESS, '*' * 70)
        upgrade_commands = upgradecheck.UpgradeCommands()
        details = upgrade_commands._get_details(result)
        wrapped = '*' * 60 + '\n  ' + '*' * 10
        self.assertEqual(wrapped, details)

    def test_check(self):
        inst = TestCommands()
        result = inst.check()
        self.assertEqual(upgradecheck.Code.FAILURE, result)


class TestMain(base.BaseTestCase):
    def _run_test(self, upgrade_command, expected):
        conf = cfg.ConfigOpts()
        result = upgradecheck.main(
            conf=conf,
            project='oslo-upgradecheck-test',
            upgrade_command=upgrade_command,
            argv=['upgrade', 'check'],
        )
        self.assertEqual(expected, result)

    def test_main(self):
        inst = TestCommands()
        self._run_test(inst, upgradecheck.Code.FAILURE)

    def test_main_exception(self):
        raises = mock.Mock()
        raises.check.side_effect = Exception('test exception')
        self._run_test(raises, 255)

    def test_main_success(self):
        inst = SuccessCommands()
        self._run_test(inst, 0)


class TestExampleFile(base.BaseTestCase):
    def test_example_main(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '../../doc/source/main.py')
        # The example includes both a passing and failing test, which means the
        # overall result is failure.
        self.assertEqual(
            upgradecheck.Code.FAILURE,
            subprocess.call([sys.executable, path, 'upgrade', 'check']))
