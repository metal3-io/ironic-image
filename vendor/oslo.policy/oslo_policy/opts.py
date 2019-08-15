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

import copy

from oslo_config import cfg

from oslo_policy._i18n import _

__all__ = [
    'list_opts',
    'set_defaults',
]

_option_group = 'oslo_policy'

_options = [
    cfg.BoolOpt('enforce_scope',
                default=False,
                help=_('This option controls whether or not to enforce scope '
                       'when evaluating policies. If ``True``, the scope of '
                       'the token used in the request is compared to the '
                       '``scope_types`` of the policy being enforced. If the '
                       'scopes do not match, an ``InvalidScope`` exception '
                       'will be raised. If ``False``, a message will be '
                       'logged informing operators that policies are being '
                       'invoked with mismatching scope.')),
    cfg.StrOpt('policy_file',
               default='policy.json',
               help=_('The relative or absolute path of a file that maps '
                      'roles to permissions for a given service. Relative '
                      'paths must be specified in relation to the '
                      'configuration file setting this option.'),
               deprecated_group='DEFAULT'),
    cfg.StrOpt('policy_default_rule',
               default='default',
               help=_('Default rule. Enforced when a requested rule is not '
                      'found.'),
               deprecated_group='DEFAULT'),
    cfg.MultiStrOpt('policy_dirs',
                    default=['policy.d'],
                    help=_('Directories where policy configuration files are '
                           'stored. They can be relative to any directory '
                           'in the search path defined by the config_dir '
                           'option, or absolute paths. The file defined by '
                           'policy_file must exist for these directories to '
                           'be searched.  Missing or empty directories are '
                           'ignored.'),
                    deprecated_group='DEFAULT'),
    cfg.StrOpt('remote_content_type',
               choices=('application/x-www-form-urlencoded',
                        'application/json'),
               default='application/x-www-form-urlencoded',
               help=_("Content Type to send and receive data for "
                      "REST based policy check")),
    cfg.BoolOpt('remote_ssl_verify_server_crt',
                help=_("server identity verification for REST based "
                       "policy check"),
                default=False),
    cfg.StrOpt('remote_ssl_ca_crt_file',
               help=_("Absolute path to ca cert file for REST based "
                      "policy check")),
    cfg.StrOpt('remote_ssl_client_crt_file',
               help=_("Absolute path to client cert for REST based "
                      "policy check")),
    cfg.StrOpt('remote_ssl_client_key_file',
               help=_("Absolute path client key file REST based "
                      "policy check")),
]


def list_opts():
    """Return a list of oslo.config options available in the library.

    The returned list includes all oslo.config options which may be registered
    at runtime by the library.
    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.
    This function is also discoverable via the 'oslo_messaging' entry point
    under the 'oslo.config.opts' namespace.
    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by this library.

    :returns: a list of (group_name, opts) tuples
    """

    return [(_option_group, copy.deepcopy(_options))]


def _register(conf):
    """Register the policy options.

    We do this in a few places, so use a function to ensure it is done
    consistently.
    """
    conf.register_opts(_options, group=_option_group)


def set_defaults(conf, policy_file=None):
    """Set defaults for configuration variables.

    Overrides default options values.

    :param conf: Configuration object, managed by the caller.
    :type conf: oslo.config.cfg.ConfigOpts

    :param policy_file: The base filename for the file that
                        defines policies.
    :type policy_file: unicode
    """
    _register(conf)

    if policy_file is not None:
        cfg.set_defaults(_options, policy_file=policy_file)
