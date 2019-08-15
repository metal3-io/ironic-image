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
import textwrap
import warnings
import yaml

from oslo_config import cfg
from oslo_serialization import jsonutils
import stevedore

from oslo_policy import policy

LOG = logging.getLogger(__name__)

GENERATOR_OPTS = [
    cfg.StrOpt('output-file',
               help='Path of the file to write to. Defaults to stdout.'),
]

RULE_OPTS = [
    cfg.MultiStrOpt('namespace',
                    required=True,
                    help='Option namespace(s) under "oslo.policy.policies" in '
                         'which to query for options.'),
    cfg.StrOpt('format',
               help='Desired format for the output.',
               default='yaml',
               choices=['json', 'yaml']),
]

ENFORCER_OPTS = [
    cfg.StrOpt('namespace',
               required=True,
               help='Option namespace under "oslo.policy.enforcer" in '
                    'which to look for a policy.Enforcer.'),
]

UPGRADE_OPTS = [
    cfg.StrOpt('policy',
               required=True,
               help='Path to the policy file which need to be updated.')
]


def get_policies_dict(namespaces):
    """Find the options available via the given namespaces.

    :param namespaces: a list of namespaces registered under
                       'oslo.policy.policies'
    :returns: a dict of {namespace1: [rule_default_1, rule_default_2],
                         namespace2: [rule_default_3]...}
    """
    mgr = stevedore.named.NamedExtensionManager(
        'oslo.policy.policies',
        names=namespaces,
        on_load_failure_callback=on_load_failure_callback,
        invoke_on_load=True)
    opts = {ep.name: ep.obj for ep in mgr}

    return opts


def _get_enforcer(namespace):
    """Find a policy.Enforcer via an entry point with the given namespace.

    :param namespace: a namespace under oslo.policy.enforcer where the desired
                      enforcer object can be found.
    :returns: a policy.Enforcer object
    """
    mgr = stevedore.named.NamedExtensionManager(
        'oslo.policy.enforcer',
        names=[namespace],
        on_load_failure_callback=on_load_failure_callback,
        invoke_on_load=True)
    if namespace not in mgr:
        raise KeyError('Namespace "%s" not found.' % namespace)
    enforcer = mgr[namespace].obj

    return enforcer


def _format_help_text(description):
    """Format a comment for a policy based on the description provided.

    :param description: A string with helpful text.
    :returns: A line wrapped comment, or blank comment if description is None
    """
    if not description:
        return '#'

    formatted_lines = []
    paragraph = []

    def _wrap_paragraph(lines):
        return textwrap.wrap(' '.join(lines), 70, initial_indent='# ',
                             subsequent_indent='# ')

    for line in description.strip().splitlines():
        if not line.strip():
            # empty line -> line break, so dump anything we have
            formatted_lines.extend(_wrap_paragraph(paragraph))
            formatted_lines.append('#')
            paragraph = []
        elif len(line) == len(line.lstrip()):
            # no leading whitespace = paragraph, which should be wrapped
            paragraph.append(line.rstrip())
        else:
            # leading whitespace - literal block, which should not be wrapping
            if paragraph:
                # ...however, literal blocks need a new line before them to
                # delineate things
                # TODO(stephenfin): Raise an exception here and stop doing
                # anything else in oslo.policy 2.0
                warnings.warn(
                    'Invalid policy description: literal blocks must be '
                    'preceded by a new line. This will raise an exception in '
                    'a future version of oslo.policy:\n%s' % description,
                    FutureWarning)
                formatted_lines.extend(_wrap_paragraph(paragraph))
                formatted_lines.append('#')
                paragraph = []

            formatted_lines.append('# %s' % line.rstrip())

    if paragraph:
        # dump anything we might still have in the buffer
        formatted_lines.extend(_wrap_paragraph(paragraph))

    return '\n'.join(formatted_lines)


def _format_rule_default_yaml(default, include_help=True):
    """Create a yaml node from policy.RuleDefault or policy.DocumentedRuleDefault.

    :param default: A policy.RuleDefault or policy.DocumentedRuleDefault object
    :returns: A string containing a yaml representation of the RuleDefault
    """
    text = ('"%(name)s": "%(check_str)s"\n' %
            {'name': default.name,
             'check_str': default.check_str})

    if include_help:
        op = ""
        if hasattr(default, 'operations'):
            for operation in default.operations:
                op += ('# %(method)s  %(path)s\n' %
                       {'method': operation['method'],
                        'path': operation['path']})
        intended_scope = ""
        if getattr(default, 'scope_types', None) is not None:
            intended_scope = (
                '# Intended scope(s): ' + ', '.join(default.scope_types) + '\n'
            )

        text = ('%(help)s\n%(op)s%(scope)s#%(text)s\n' %
                {'help': _format_help_text(default.description),
                 'op': op,
                 'scope': intended_scope,
                 'text': text})

    if default.deprecated_for_removal:
        text = (
            '# DEPRECATED\n# "%(name)s" has been deprecated since '
            '%(since)s.\n%(reason)s\n%(text)s'
        ) % {'name': default.name,
             'check_str': default.check_str,
             'since': default.deprecated_since,
             'reason': _format_help_text(default.deprecated_reason),
             'text': text}
    elif default.deprecated_rule:
        # This issues a deprecation warning but aliases the old policy name
        # with the new policy name for compatibility.
        deprecated_text = (
            'DEPRECATED\n"%(old_name)s":"%(old_check_str)s" has been '
            'deprecated since %(since)s in favor of '
            '"%(name)s":"%(check_str)s".\n%(reason)s'
        ) % {'old_name': default.deprecated_rule.name,
             'old_check_str': default.deprecated_rule.check_str,
             'since': default.deprecated_since,
             'name': default.name,
             'check_str': default.check_str,
             'reason': default.deprecated_reason}

        text = (
            '%(text)s%(deprecated_text)s\n"%(old_name)s": "rule:%(name)s"\n'
        ) % {'text': text,
             'deprecated_text': _format_help_text(deprecated_text),
             'old_name': default.deprecated_rule.name,
             'name': default.name}

    return text


def _format_rule_default_json(default):
    """Create a json node from policy.RuleDefault or policy.DocumentedRuleDefault.

    :param default: A policy.RuleDefault or policy.DocumentedRuleDefault object
    :returns: A string containing a json representation of the RuleDefault
    """
    return ('"%(name)s": "%(check_str)s"' %
            {'name': default.name,
             'check_str': default.check_str})


def _sort_and_format_by_section(policies, output_format='yaml',
                                include_help=True):
    """Generate a list of policy section texts

    The text for a section will be created and returned one at a time. The
    sections are sorted first to provide for consistent output.

    Text is created in yaml format. This is done manually because PyYaml
    does not facilitate outputing comments.

    :param policies: A dict of {section1: [rule_default_1, rule_default_2],
                                section2: [rule_default_3]}
    :param output_format: The format of the file to output to.
    """
    for section in sorted(policies.keys()):
        rule_defaults = policies[section]
        for rule_default in rule_defaults:
            if output_format == 'yaml':
                yield _format_rule_default_yaml(rule_default,
                                                include_help=include_help)
            elif output_format == 'json':
                yield _format_rule_default_json(rule_default)


def _generate_sample(namespaces, output_file=None, output_format='yaml',
                     include_help=True):
    """Generate a sample policy file.

    List all of the policies available via the namespace specified in the
    given configuration and write them to the specified output file.

    :param namespaces: a list of namespaces registered under
                       'oslo.policy.policies'. Stevedore will look here for
                       policy options.
    :param output_file: The path of a file to output to. stdout used if None.
    :param output_format: The format of the file to output to.
    :param include_help: True, generates a sample-policy file with help text
                         along with rules in which everything is commented out.
                         False, generates a sample-policy file with only rules.
    """
    policies = get_policies_dict(namespaces)

    output_file = (open(output_file, 'w') if output_file
                   else sys.stdout)

    sections_text = []
    for section in _sort_and_format_by_section(policies, output_format,
                                               include_help=include_help):
        sections_text.append(section)

    if output_format == 'yaml':
        output_file.writelines(sections_text)
    elif output_format == 'json':
        output_file.writelines((
            '{\n    ',
            ',\n    '.join(sections_text),
            '\n}\n'))


def _generate_policy(namespace, output_file=None):
    """Generate a policy file showing what will be used.

    This takes all registered policies and merges them with what's defined in
    a policy file and outputs the result. That result is the effective policy
    that will be honored by policy checks.

    :param output_file: The path of a file to output to. stdout used if None.
    """
    enforcer = _get_enforcer(namespace)
    # Ensure that files have been parsed
    enforcer.load_rules()

    file_rules = [policy.RuleDefault(name, default.check_str)
                  for name, default in enforcer.file_rules.items()]
    registered_rules = [policy.RuleDefault(name, default.check_str)
                        for name, default in enforcer.registered_rules.items()
                        if name not in enforcer.file_rules]
    policies = {'rules': file_rules + registered_rules}

    output_file = (open(output_file, 'w') if output_file
                   else sys.stdout)

    for section in _sort_and_format_by_section(policies, include_help=False):
        output_file.write(section)


def _list_redundant(namespace):
    """Generate a list of configured policies which match defaults.

    This checks all policies loaded from policy files and checks to see if they
    match registered policies. If so then it is redundant to have them defined
    in a policy file and operators should consider removing them.
    """
    enforcer = _get_enforcer(namespace)
    # Ensure that files have been parsed
    enforcer.load_rules()

    for name, file_rule in enforcer.file_rules.items():
        reg_rule = enforcer.registered_rules.get(name, None)
        if reg_rule:
            if file_rule == reg_rule:
                print(reg_rule)


def on_load_failure_callback(*args, **kwargs):
    raise


def generate_sample(args=None):
    logging.basicConfig(level=logging.WARN)
    conf = cfg.ConfigOpts()
    conf.register_cli_opts(GENERATOR_OPTS + RULE_OPTS)
    conf.register_opts(GENERATOR_OPTS + RULE_OPTS)
    conf(args)
    _generate_sample(conf.namespace, conf.output_file, conf.format)


def generate_policy(args=None):
    logging.basicConfig(level=logging.WARN)
    conf = cfg.ConfigOpts()
    conf.register_cli_opts(GENERATOR_OPTS + ENFORCER_OPTS)
    conf.register_opts(GENERATOR_OPTS + ENFORCER_OPTS)
    conf(args)
    _generate_policy(conf.namespace, conf.output_file)


def _upgrade_policies(policies, default_policies):
    old_policies_keys = list(policies.keys())
    for section in sorted(default_policies.keys()):
        rule_defaults = default_policies[section]
        for rule_default in rule_defaults:
            if (rule_default.deprecated_rule and
                    rule_default.deprecated_rule.name in old_policies_keys):
                policies[rule_default.name] = policies.pop(
                    rule_default.deprecated_rule.name)
                LOG.info('The name of policy %(old_name)s has been upgraded to'
                         '%(new_name)',
                         {'old_name': rule_default.deprecated_rule.name,
                          'new_name': rule_default.name})


def upgrade_policy(args=None):
    logging.basicConfig(level=logging.WARN)
    conf = cfg.ConfigOpts()
    conf.register_cli_opts(GENERATOR_OPTS + RULE_OPTS + UPGRADE_OPTS)
    conf.register_opts(GENERATOR_OPTS + RULE_OPTS + UPGRADE_OPTS)
    conf(args)
    with open(conf.policy, 'r') as input_data:
        policies = policy.parse_file_contents(input_data.read())
    default_policies = get_policies_dict(conf.namespace)

    _upgrade_policies(policies, default_policies)

    if conf.output_file:
        if conf.format == 'yaml':
            yaml.safe_dump(policies, open(conf.output_file, 'w'),
                           default_flow_style=False)
        elif conf.format == 'json':
            jsonutils.dump(policies, open(conf.output_file, 'w'),
                           indent=4)
    else:
        if conf.format == 'yaml':
            sys.stdout.write(yaml.safe_dump(policies,
                                            default_flow_style=False))
        elif conf.format == 'json':
            sys.stdout.write(jsonutils.dumps(policies, indent=4))


def list_redundant(args=None):
    logging.basicConfig(level=logging.WARN)
    conf = cfg.ConfigOpts()
    conf.register_cli_opts(ENFORCER_OPTS)
    conf.register_opts(ENFORCER_OPTS)
    conf(args)
    _list_redundant(conf.namespace)
