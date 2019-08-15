# Copyright 2018 Red Hat Inc.
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

"""Example CLI command for running upgrade checks"""

import sys

from oslo_config import cfg
from oslo_upgradecheck import upgradecheck


class Checks(upgradecheck.UpgradeCommands):
    def success(self):
        return upgradecheck.Result(upgradecheck.Code.SUCCESS,
                                   'Always succeeds')

    def failure(self):
        return upgradecheck.Result(upgradecheck.Code.FAILURE, 'Always fails')

    _upgrade_checks = (('always succeeds', success),
                       ('always fails', failure),
                       )


def main():
    return upgradecheck.main(
        conf=cfg.CONF,
        project='myprojectname',
        upgrade_command=Checks(),
    )


if __name__ == '__main__':
    sys.exit(main())
