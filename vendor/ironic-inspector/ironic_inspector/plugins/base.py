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

"""Base code for plugins support."""

import abc

from oslo_config import cfg
from oslo_log import log
import six
import stevedore

from ironic_inspector.common.i18n import _


CONF = cfg.CONF
LOG = log.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class ProcessingHook(object):  # pragma: no cover
    """Abstract base class for introspection data processing hooks."""

    dependencies = []
    """An ordered list of hooks that must be enabled before this one.

    The items here should be entry point names, not classes.
    """

    def before_processing(self, introspection_data, **kwargs):
        """Hook to run before any other data processing.

        This hook is run even before sanity checks.

        :param introspection_data: raw information sent by the ramdisk,
                                   may be modified by the hook.
        :param kwargs: used for extensibility without breaking existing hooks
        :returns: nothing.
        """

    def before_update(self, introspection_data, node_info, **kwargs):
        """Hook to run before Ironic node update.

        This hook is run after node is found and ports are created,
        just before the node is updated with the data.

        :param introspection_data: processed data from the ramdisk.
        :param node_info: NodeInfo instance.
        :param kwargs: used for extensibility without breaking existing hooks.
        :returns: nothing.

        [RFC 6902] - http://tools.ietf.org/html/rfc6902
        """


class WithValidation(object):
    REQUIRED_PARAMS = set()
    """Set with names of required parameters."""

    OPTIONAL_PARAMS = set()
    """Set with names of optional parameters."""

    def validate(self, params, **kwargs):
        """Validate params passed during creation.

        Default implementation checks for presence of fields from
        REQUIRED_PARAMS and fails for unexpected fields (not from
        REQUIRED_PARAMS + OPTIONAL_PARAMS).

        :param params: params as a dictionary
        :param kwargs: used for extensibility without breaking existing plugins
        :raises: ValueError on validation failure
        """
        passed = {k for k, v in params.items() if v is not None}
        missing = self.REQUIRED_PARAMS - passed
        unexpected = passed - self.REQUIRED_PARAMS - self.OPTIONAL_PARAMS

        msg = []
        if missing:
            msg.append(_('missing required parameter(s): %s')
                       % ', '.join(missing))
        if unexpected:
            msg.append(_('unexpected parameter(s): %s')
                       % ', '.join(unexpected))

        if msg:
            raise ValueError('; '.join(msg))


@six.add_metaclass(abc.ABCMeta)
class RuleConditionPlugin(WithValidation):  # pragma: no cover
    """Abstract base class for rule condition plugins."""

    REQUIRED_PARAMS = {'value'}

    ALLOW_NONE = False
    """Whether this condition accepts None when field is not found."""

    @abc.abstractmethod
    def check(self, node_info, field, params, **kwargs):
        """Check if condition holds for a given field.

        :param node_info: NodeInfo object
        :param field: field value
        :param params: parameters as a dictionary, changing it here will change
                       what will be stored in database
        :param kwargs: used for extensibility without breaking existing plugins
        :raises ValueError: on unacceptable field value
        :returns: True if check succeeded, otherwise False
        """


@six.add_metaclass(abc.ABCMeta)
class RuleActionPlugin(WithValidation):  # pragma: no cover
    """Abstract base class for rule action plugins."""

    FORMATTED_PARAMS = []
    """List of params will be formatted with python format."""

    @abc.abstractmethod
    def apply(self, node_info, params, **kwargs):
        """Run action on successful rule match.

        :param node_info: NodeInfo object
        :param params: parameters as a dictionary
        :param kwargs: used for extensibility without breaking existing plugins
        :raises: utils.Error on failure
        """


_HOOKS_MGR = None
_NOT_FOUND_HOOK_MGR = None
_CONDITIONS_MGR = None
_ACTIONS_MGR = None
_INTROSPECTION_DATA_MGR = None


def reset():
    """Reset cached managers."""
    global _HOOKS_MGR
    global _NOT_FOUND_HOOK_MGR
    global _CONDITIONS_MGR
    global _ACTIONS_MGR
    global _INTROSPECTION_DATA_MGR

    _HOOKS_MGR = None
    _NOT_FOUND_HOOK_MGR = None
    _CONDITIONS_MGR = None
    _ACTIONS_MGR = None
    _INTROSPECTION_DATA_MGR = None


def missing_entrypoints_callback(names):
    """Raise MissingHookError with comma-separated list of missing hooks"""
    error = _('The following hook(s) are missing or failed to load: %s')
    raise RuntimeError(error % ', '.join(names))


def processing_hooks_manager(*args):
    """Create a Stevedore extension manager for processing hooks.

    :param args: arguments to pass to the hooks constructor.
    """
    global _HOOKS_MGR
    if _HOOKS_MGR is None:
        names = [x.strip()
                 for x in CONF.processing.processing_hooks.split(',')
                 if x.strip()]
        _HOOKS_MGR = stevedore.NamedExtensionManager(
            'ironic_inspector.hooks.processing',
            names=names,
            invoke_on_load=True,
            invoke_args=args,
            on_missing_entrypoints_callback=missing_entrypoints_callback,
            name_order=True)
    return _HOOKS_MGR


def validate_processing_hooks():
    """Validate the enabled processing hooks.

    :raises: MissingHookError on missing or failed to load hooks
    :raises: RuntimeError on validation failure
    :returns: the list of hooks passed validation
    """
    hooks = [ext for ext in processing_hooks_manager()]
    enabled = set()
    errors = []
    for hook in hooks:
        deps = getattr(hook.obj, 'dependencies', ())
        missing = [d for d in deps if d not in enabled]
        if missing:
            errors.append('Hook %(hook)s requires the following hooks to be '
                          'enabled before it: %(deps)s. The following hooks '
                          'are missing: %(missing)s.' %
                          {'hook': hook.name,
                           'deps': ', '.join(deps),
                           'missing': ', '.join(missing)})
        enabled.add(hook.name)

    if errors:
        raise RuntimeError("Some hooks failed to load due to dependency "
                           "problems:\n%s" % "\n".join(errors))

    return hooks


def node_not_found_hook_manager(*args):
    global _NOT_FOUND_HOOK_MGR
    if _NOT_FOUND_HOOK_MGR is None:
        name = CONF.processing.node_not_found_hook
        if name:
            _NOT_FOUND_HOOK_MGR = stevedore.DriverManager(
                'ironic_inspector.hooks.node_not_found',
                name=name)

    return _NOT_FOUND_HOOK_MGR


def rule_conditions_manager():
    """Create a Stevedore extension manager for conditions in rules."""
    global _CONDITIONS_MGR
    if _CONDITIONS_MGR is None:
        _CONDITIONS_MGR = stevedore.ExtensionManager(
            'ironic_inspector.rules.conditions',
            invoke_on_load=True)
    return _CONDITIONS_MGR


def rule_actions_manager():
    """Create a Stevedore extension manager for actions in rules."""
    global _ACTIONS_MGR
    if _ACTIONS_MGR is None:
        _ACTIONS_MGR = stevedore.ExtensionManager(
            'ironic_inspector.rules.actions',
            invoke_on_load=True)
    return _ACTIONS_MGR


def introspection_data_manager():
    global _INTROSPECTION_DATA_MGR
    if _INTROSPECTION_DATA_MGR is None:
        _INTROSPECTION_DATA_MGR = stevedore.ExtensionManager(
            'ironic_inspector.introspection_data.store',
            invoke_on_load=True)
    return _INTROSPECTION_DATA_MGR
