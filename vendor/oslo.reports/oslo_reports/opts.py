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

from oslo_reports._i18n import _

__all__ = [
    'list_opts',
    'set_defaults',
]


_option_group = 'oslo_reports'

_options = [
    cfg.StrOpt('log_dir',
               help=_('Path to a log directory where to create a file')),
    cfg.StrOpt('file_event_handler',
               help=_('The path to a file to watch for changes to trigger '
                      'the reports, instead of signals. Setting this option '
                      'disables the signal trigger for the reports. If '
                      'application is running as a WSGI application it is '
                      'recommended to use this instead of signals.')),
    cfg.IntOpt('file_event_handler_interval',
               default=1,
               help=_('How many seconds to wait between polls when '
                      'file_event_handler is set'))
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


def set_defaults(conf):
    """Set defaults for configuration variables.

    Overrides default options values.

    :param conf: Configuration object, managed by the caller.
    :type conf: oslo.config.cfg.ConfigOpts
    """
    conf.register_opts(_options, group=_option_group)
