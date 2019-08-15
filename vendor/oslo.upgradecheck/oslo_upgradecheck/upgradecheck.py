# Copyright 2018 Red Hat Inc.
# Copyright 2016 IBM Corp.
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

import json
import sys
import textwrap
import traceback

import enum
from oslo_config import cfg
import prettytable
import six

from oslo_upgradecheck._i18n import _

CONF = None


class Code(enum.IntEnum):
    """Status codes for the upgrade check command"""

    # All upgrade readiness checks passed successfully and there is
    # nothing to do.
    SUCCESS = 0

    # At least one check encountered an issue and requires further
    # investigation. This is considered a warning but the upgrade may be OK.
    WARNING = 1

    # There was an upgrade status check failure that needs to be
    # investigated. This should be considered something that stops an upgrade.
    FAILURE = 2


UPGRADE_CHECK_MSG_MAP = {
    Code.SUCCESS: _('Success'),
    Code.WARNING: _('Warning'),
    Code.FAILURE: _('Failure'),
}


class Result(object):
    """Class used for 'nova-status upgrade check' results.

    The 'code' attribute is a Code enum.
    The 'details' attribute is a translated message generally only used for
    checks that result in a warning or failure code. The details should provide
    information on what issue was discovered along with any remediation.
    """

    def __init__(self, code, details=None):
        super(Result, self).__init__()
        self.code = code
        self.details = details


class UpgradeCommands(object):
    """Base class for upgrade checks

    This class should be inherited by a class in each project that provides
    the actual checks. Those checks should be added to the _upgrade_checks
    class member so that they are run when the ``check`` method is called.

    The subcommands here must not rely on the service object model since they
    should be able to run on n-1 data. Any queries to the database should be
    done through the sqlalchemy query language directly like the database
    schema migrations.
    """
    display_title = _('Upgrade Check Results')
    _upgrade_checks = ()

    def _get_details(self, upgrade_check_result):
        if upgrade_check_result.details is not None:
            # wrap the text on the details to 60 characters
            return '\n'.join(textwrap.wrap(upgrade_check_result.details, 60,
                                           subsequent_indent='  '))

    def check(self):
        """Performs checks to see if the deployment is ready for upgrade.

        These checks are expected to be run BEFORE services are restarted with
        new code.

        :returns: Code
        """
        return_code = Code.SUCCESS
        # This is a list if 2-item tuples for the check name and it's results.
        check_results = []
        for name, func in self._upgrade_checks:
            result = func(self)
            # store the result of the check for the summary table
            check_results.append((name, result))
            # we want to end up with the highest level code of all checks
            if result.code > return_code:
                return_code = result.code

        # We're going to build a summary table that looks like:
        # +----------------------------------------------------+
        # | Upgrade Check Results                              |
        # +----------------------------------------------------+
        # | Check: Cells v2                                    |
        # | Result: Success                                    |
        # | Details: None                                      |
        # +----------------------------------------------------+
        # | Check: Placement API                               |
        # | Result: Failure                                    |
        # | Details: There is no placement-api endpoint in the |
        # |          service catalog.                          |
        # +----------------------------------------------------+

        # Since registering opts can be overridden by consuming code, we can't
        # assume that our locally defined option exists.
        if (hasattr(CONF, 'command') and hasattr(CONF.command, 'json') and
                CONF.command.json):
            # NOTE(bnemec): We use six.text_type on the translated string to
            # force immediate translation if lazy translation is in use.
            # See lp1801761 for details.
            output = {'name': six.text_type(self.display_title), 'checks': []}
            for name, result in check_results:
                output['checks'].append(
                    {'check': name,
                     'result': result.code,
                     'details': result.details}
                )
            print(json.dumps(output))
        else:
            # NOTE(bnemec): We use six.text_type on the translated string to
            # force immediate translation if lazy translation is in use.
            # See lp1801761 for details.
            t = prettytable.PrettyTable([six.text_type(self.display_title)],
                                        hrules=prettytable.ALL)
            t.align = 'l'
            for name, result in check_results:
                cell = (
                    _('Check: %(name)s\n'
                      'Result: %(result)s\n'
                      'Details: %(details)s') %
                    {
                        'name': name,
                        'result': UPGRADE_CHECK_MSG_MAP[result.code],
                        'details': self._get_details(result),
                    }
                )
                t.add_row([cell])
            print(t)

        return return_code


def register_cli_options(conf, upgrade_command):
    """Set up the command line options.

    Adds a subcommand to support 'upgrade check' on the command line.

    :param conf: An oslo.confg ConfigOpts instance on which to register the
                 upgrade check arguments.
    :param upgrade_command: The UpgradeCommands instance.
    """
    def add_parsers(subparsers):
        upgrade_action = subparsers.add_parser('upgrade')
        upgrade_action.add_argument('check')
        upgrade_action.set_defaults(action_fn=upgrade_command.check)
        upgrade_action.add_argument(
            '--json',
            action='store_true',
            help='Output the results in JSON format. Default is to print '
                 'results in human readable table format.')

    opt = cfg.SubCommandOpt('command', handler=add_parsers)
    conf.register_cli_opt(opt)


def run(conf):
    """Run the requested command.

    :param conf: An oslo.confg ConfigOpts instance on which the upgrade
                 commands have been previously registered.
    """
    try:
        return conf.command.action_fn()
    except Exception:
        print(_('Error:\n%s') % traceback.format_exc())
        # This is 255 so it's not confused with the upgrade check exit codes.
        return 255


def main(conf, project, upgrade_command,
         argv=sys.argv[1:],
         default_config_files=None):
    """Simple implementation of main for upgrade checks

    This can be used in upgrade check commands to provide the minimum
    necessary parameter handling and logic.

    :param conf: An oslo.confg ConfigOpts instance on which to register the
                 upgrade check arguments.
    :param project: The name of the project, to be used as an argument
                    to the oslo_config.ConfigOpts instance to find
                    configuration files.
    :param upgrade_command: The UpgradeCommands instance.
    :param argv: The command line arguments to parse. Defaults to sys.argv[1:].
    :param default_config_files: The configuration files to load. For projects
                                 that use non-standard default locations for
                                 the configuration files, use this to override
                                 the search behavior in oslo.config.

    """
    global CONF
    register_cli_options(conf, upgrade_command)

    conf(
        args=argv,
        project=project,
        default_config_files=default_config_files,
    )
    CONF = conf
    return run(conf)
