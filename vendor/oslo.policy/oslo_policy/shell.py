#!/usr/bin/env python

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

import collections
import sys

from oslo_serialization import jsonutils

from oslo_config import cfg
from oslo_policy import opts
from oslo_policy import policy


class FakeEnforcer(object):
    def __init__(self, rules, config):
        self.rules = rules
        self.conf = None

        if config:
            self.conf = cfg.ConfigOpts()

            for group, options in opts.list_opts():
                self.conf.register_opts(options, group)

            self.conf(["--config-file={}".format(config)])


def _try_rule(key, rule, target, access_data, o):
    try:
        result = rule(target, access_data, o, current_rule=key)
        if result:
            print("passed: %s" % key)
        else:
            print("failed: %s" % key)
    except Exception as e:
        print(e)
        print("exception: %s" % rule)


def flatten(d, parent_key=''):
    """Flatten a nested dictionary

    Converts a dictionary with nested values to a single level flat
    dictionary, with dotted notation for each key.

    """
    items = []
    for k, v in d.items():
        new_key = parent_key + '.' + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)


def tool(policy_file, access_file, apply_rule, is_admin=False,
         target_file=None, enforcer_config=None):

    with open(access_file, "rb", 0) as a:
        access = a.read()

    access_data = jsonutils.loads(access)['token']
    access_data['roles'] = [role['name'] for role in access_data['roles']]
    access_data['project_id'] = access_data['project']['id']
    access_data['is_admin'] = is_admin

    with open(policy_file, "rb", 0) as p:
        policy_data = p.read()

    rules = policy.Rules.load(policy_data, "default")

    enforcer = FakeEnforcer(rules, enforcer_config)

    if target_file:
        with open(target_file, "rb", 0) as t:
            target = t.read()

        target_data = flatten(jsonutils.loads(target))
    else:
        target_data = {"project_id": access_data['project_id']}

    if apply_rule:
        key = apply_rule
        rule = rules[apply_rule]
        _try_rule(key, rule, target_data, access_data, enforcer)
        return

    for key, rule in sorted(rules.items()):
        if ":" in key:
            _try_rule(key, rule, target_data, access_data, enforcer)


def main():
    conf = cfg.ConfigOpts()

    conf.register_cli_opt(cfg.StrOpt(
        'policy',
        required=True,
        help='path to a policy file.'))

    conf.register_cli_opt(cfg.StrOpt(
        'access',
        required=True,
        help='path to a file containing OpenStack Identity API '
             'access info in JSON format.'))

    conf.register_cli_opt(cfg.StrOpt(
        'target',
        help='path to a file containing custom target info in '
             'JSON format. This will be used to evaluate the policy with.'))

    conf.register_cli_opt(cfg.StrOpt(
        'rule',
        help='rule to test.'))

    conf.register_cli_opt(cfg.BoolOpt(
        'is_admin',
        help='set is_admin=True on the credentials used for the evaluation.',
        default=False))

    conf.register_cli_opt(cfg.StrOpt(
        'enforcer_config',
        help='configuration file for the oslopolicy-checker enforcer'))

    conf()

    tool(conf.policy, conf.access, conf.rule, conf.is_admin,
         conf.target, conf.enforcer_config)


if __name__ == "__main__":
    sys.exit(main())
