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

import itertools
import sys

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_policy import policy

CONF = cfg.CONF

_ENFORCER = None

default_policies = [
    policy.RuleDefault(
        'is_admin',
        'role:admin or role:administrator or role:baremetal_admin',
        description='Full read/write API access'),
    policy.RuleDefault(
        'is_observer',
        'role:baremetal_observer',
        description='Read-only API access'),
    policy.RuleDefault(
        'public_api',
        'is_public_api:True',
        description='Internal flag for public API routes'),
    policy.RuleDefault(
        'default',
        '!',
        description='Default API access policy'),
]

api_version_policies = [
    policy.DocumentedRuleDefault(
        'introspection',
        'rule:public_api',
        'Access the API root for available versions information',
        [{'path': '/', 'method': 'GET'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:version',
        'rule:public_api',
        'Access the versioned API root for version information',
        [{'path': '/{version}', 'method': 'GET'}]
    ),
]


introspection_policies = [
    policy.DocumentedRuleDefault(
        'introspection:continue',
        'rule:public_api',
        'Ramdisk callback to continue introspection',
        [{'path': '/continue', 'method': 'POST'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:status',
        'rule:is_admin or rule:is_observer',
        'Get introspection status',
        [{'path': '/introspection', 'method': 'GET'},
         {'path': '/introspection/{node_id}', 'method': 'GET'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:start',
        'rule:is_admin',
        'Start introspection',
        [{'path': '/introspection/{node_id}', 'method': 'POST'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:abort',
        'rule:is_admin',
        'Abort introspection',
        [{'path': '/introspection/{node_id}/abort', 'method': 'POST'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:data',
        'rule:is_admin',
        'Get introspection data',
        [{'path': '/introspection/{node_id}/data', 'method': 'GET'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:reapply',
        'rule:is_admin',
        'Reapply introspection on stored data',
        [{'path': '/introspection/{node_id}/data/unprocessed',
          'method': 'POST'}]
    ),
]

rule_policies = [
    policy.DocumentedRuleDefault(
        'introspection:rule:get',
        'rule:is_admin',
        'Get introspection rule(s)',
        [{'path': '/rules', 'method': 'GET'},
         {'path': '/rules/{rule_id}', 'method': 'GET'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:rule:delete',
        'rule:is_admin',
        'Delete introspection rule(s)',
        [{'path': '/rules', 'method': 'DELETE'},
         {'path': '/rules/{rule_id}', 'method': 'DELETE'}]
    ),
    policy.DocumentedRuleDefault(
        'introspection:rule:create',
        'rule:is_admin',
        'Create introspection rule',
        [{'path': '/rules', 'method': 'POST'}]
    ),
]


def list_policies():
    """Get list of all policies defined in code.

    Used to register them all at runtime,
    and by oslo-config-generator to generate sample policy files.
    """
    policies = itertools.chain(
        default_policies,
        api_version_policies,
        introspection_policies,
        rule_policies)
    return policies


@lockutils.synchronized('policy_enforcer')
def init_enforcer(policy_file=None, rules=None,
                  default_rule=None, use_conf=True):
    """Synchronously initializes the policy enforcer

       :param policy_file: Custom policy file to use, if none is specified,
                           `CONF.oslo_policy.policy_file` will be used.
       :param rules: Default dictionary / Rules to use. It will be
                     considered just in the first instantiation.
       :param default_rule: Default rule to use,
                            CONF.oslo_policy.policy_default_rule will
                            be used if none is specified.
       :param use_conf: Whether to load rules from config file.
    """
    global _ENFORCER

    if _ENFORCER:
        return
    _ENFORCER = policy.Enforcer(CONF, policy_file=policy_file,
                                rules=rules,
                                default_rule=default_rule,
                                use_conf=use_conf)
    _ENFORCER.register_defaults(list_policies())


def get_enforcer():
    """Provides access to the single instance of Policy enforcer."""
    if not _ENFORCER:
        init_enforcer()
    return _ENFORCER


def get_oslo_policy_enforcer():
    """Get the enforcer instance to generate policy files.

    This method is for use by oslopolicy CLI scripts.
    Those scripts need the 'output-file' and 'namespace' options,
    but having those in sys.argv means loading the inspector config options
    will fail as those are not expected to be present.
    So we pass in an arg list with those stripped out.
    """

    conf_args = []
    # Start at 1 because cfg.CONF expects the equivalent of sys.argv[1:]
    i = 1
    while i < len(sys.argv):
        if sys.argv[i].strip('-') in ['namespace', 'output-file']:
            # e.g. --namespace <somestring>
            i += 2
            continue
        conf_args.append(sys.argv[i])
        i += 1

    cfg.CONF(conf_args, project='ironic-inspector')

    return get_enforcer()


def authorize(rule, target, creds, *args, **kwargs):
    """A shortcut for policy.Enforcer.authorize()

    Checks authorization of a rule against the target and credentials, and
    raises an exception if the rule is not defined.
    args and kwargs are passed directly to oslo.policy Enforcer.authorize
    Always returns True if CONF.auth_strategy != keystone.

    :param rule: name of a registered oslo.policy rule
    :param target: dict-like structure to check rule against
    :param creds: dict of policy values from request
    :returns: True if request is authorized against given policy,
              False otherwise
    :raises: oslo_policy.policy.PolicyNotRegistered if supplied policy
             is not registered in oslo_policy
    """
    if CONF.auth_strategy != 'keystone':
        return True
    enforcer = get_enforcer()
    rule = CONF.oslo_policy.policy_default_rule if rule is None else rule
    return enforcer.authorize(rule, target, creds, *args, **kwargs)
