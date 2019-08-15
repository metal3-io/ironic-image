# Copyright 2015 Cisco Systems
# All Rights Reserved.
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

import os
import sys

from alembic import command as alembic_command
from alembic import config as alembic_config
from alembic import util as alembic_util
from oslo_config import cfg
from oslo_log import log
import six

from ironic_inspector import conf  # noqa

CONF = cfg.CONF


def add_alembic_command(subparsers, name):
    return subparsers.add_parser(
        name, help=getattr(alembic_command, name).__doc__)


def add_command_parsers(subparsers):
    for name in ['current', 'history', 'branches', 'heads']:
        parser = add_alembic_command(subparsers, name)
        parser.set_defaults(func=do_alembic_command)

    for name in ['stamp', 'show', 'edit']:
        parser = add_alembic_command(subparsers, name)
        parser.set_defaults(func=with_revision)
        parser.add_argument('--revision', nargs='?', required=True)

    parser = add_alembic_command(subparsers, 'upgrade')
    parser.set_defaults(func=with_revision)
    parser.add_argument('--revision', nargs='?')

    parser = add_alembic_command(subparsers, 'revision')
    parser.set_defaults(func=do_revision)
    parser.add_argument('-m', '--message')
    parser.add_argument('--autogenerate', action='store_true')


command_opt = cfg.SubCommandOpt('command',
                                title='Command',
                                help='Available commands',
                                handler=add_command_parsers)


def _get_alembic_config():
    base_path = os.path.split(os.path.dirname(__file__))[0]
    return alembic_config.Config(os.path.join(base_path, 'alembic.ini'))


def do_revision(config, cmd, *args, **kwargs):
    do_alembic_command(config, cmd, message=CONF.command.message,
                       autogenerate=CONF.command.autogenerate)


def with_revision(config, cmd, *args, **kwargs):
    revision = CONF.command.revision or 'head'
    do_alembic_command(config, cmd, revision)


def do_alembic_command(config, cmd, *args, **kwargs):
    try:
        getattr(alembic_command, cmd)(config, *args, **kwargs)
    except alembic_util.CommandError as e:
        alembic_util.err(six.text_type(e))


def main(args=sys.argv[1:]):
    log.register_options(CONF)
    CONF.register_cli_opt(command_opt)
    CONF(args, project='ironic-inspector')
    config = _get_alembic_config()
    config.set_main_option('script_location', "ironic_inspector:migrations")
    config.ironic_inspector_config = CONF

    CONF.command.func(config, CONF.command.name)
