# -*- coding: utf-8 -*-
#
# Copyright (c) 2015 OpenStack Foundation.
# All Rights Reserved.
#
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

import abc
import ast
import inspect

import six
import stevedore

if hasattr(inspect, 'getfullargspec'):
    getargspec = inspect.getfullargspec
else:
    getargspec = inspect.getargspec

registered_checks = {}
extension_checks = None


def get_extensions():
    global extension_checks
    if extension_checks is None:
        em = stevedore.ExtensionManager('oslo.policy.rule_checks',
                                        invoke_on_load=False)
        extension_checks = {
            extension.name: extension.plugin
            for extension in em
        }
    return extension_checks


def _check(rule, target, creds, enforcer, current_rule):
    """Evaluate the rule.

    This private method is meant to be used by the enforcer to call
    the rule. It can also be used by built-in checks that have nested
    rules.

    We use a private function because it makes it easier to change the
    API without having an impact on subclasses not defined within the
    oslo.policy library.

    We don't put this logic in Enforcer.enforce() and invoke that
    method recursively because that changes the BaseCheck API to
    require that the enforcer argument to __call__() be a valid
    Enforcer instance (as evidenced by all of the breaking unit
    tests).

    We don't put this in a private method of BaseCheck because that
    propagates the problem of extending the list of arguments to
    __call__() if subclasses change the implementation of the
    function.

    :param rule: A check object.
    :type rule: BaseCheck
    :param target: Attributes of the object of the operation.
    :type target: dict
    :param creds: Attributes of the user performing the operation.
    :type creds: dict
    :param enforcer: The Enforcer being used.
    :type enforcer: Enforcer
    :param current_rule: The name of the policy being checked.
    :type current_rule: str

    """
    # Evaluate the rule
    argspec = getargspec(rule.__call__)
    rule_args = [target, creds, enforcer]
    # Check if the rule argument must be included or not
    if len(argspec.args) > 4:
        rule_args.append(current_rule)
    return rule(*rule_args)


@six.add_metaclass(abc.ABCMeta)
class BaseCheck(object):
    """Abstract base class for Check classes."""

    @abc.abstractmethod
    def __str__(self):
        """String representation of the Check tree rooted at this node."""

        pass

    @abc.abstractmethod
    def __call__(self, target, cred, enforcer, current_rule=None):
        """Triggers if instance of the class is called.

        Performs the check. Returns False to reject the access or a
        true value (not necessary True) to accept the access.
        """

        pass


class FalseCheck(BaseCheck):
    """A policy check that always returns ``False`` (disallow)."""

    def __str__(self):
        """Return a string representation of this check."""

        return '!'

    def __call__(self, target, cred, enforcer, current_rule=None):
        """Check the policy."""

        return False


class TrueCheck(BaseCheck):
    """A policy check that always returns ``True`` (allow)."""

    def __str__(self):
        """Return a string representation of this check."""

        return '@'

    def __call__(self, target, cred, enforcer, current_rule=None):
        """Check the policy."""

        return True


class Check(BaseCheck):
    def __init__(self, kind, match):
        self.kind = kind
        self.match = match

    def __str__(self):
        """Return a string representation of this check."""

        return '%s:%s' % (self.kind, self.match)


class NotCheck(BaseCheck):
    def __init__(self, rule):
        self.rule = rule

    def __str__(self):
        """Return a string representation of this check."""

        return 'not %s' % self.rule

    def __call__(self, target, cred, enforcer, current_rule=None):
        """Check the policy.

        Returns the logical inverse of the wrapped check.
        """

        return not _check(self.rule, target, cred, enforcer, current_rule)


class AndCheck(BaseCheck):
    def __init__(self, rules):
        self.rules = rules

    def __str__(self):
        """Return a string representation of this check."""

        return '(%s)' % ' and '.join(str(r) for r in self.rules)

    def __call__(self, target, cred, enforcer, current_rule=None):
        """Check the policy.

        Requires that all rules accept in order to return True.
        """

        for rule in self.rules:
            if not _check(rule, target, cred, enforcer, current_rule):
                return False

        return True

    def add_check(self, rule):
        """Adds rule to be tested.

        Allows addition of another rule to the list of rules that will
        be tested.

        :returns: self
        :rtype: :class:`.AndCheck`
        """

        self.rules.append(rule)
        return self


class OrCheck(BaseCheck):
    def __init__(self, rules):
        self.rules = rules

    def __str__(self):
        """Return a string representation of this check."""

        return '(%s)' % ' or '.join(str(r) for r in self.rules)

    def __call__(self, target, cred, enforcer, current_rule=None):
        """Check the policy.

        Requires that at least one rule accept in order to return True.
        """

        for rule in self.rules:
            if _check(rule, target, cred, enforcer, current_rule):
                return True
        return False

    def add_check(self, rule):
        """Adds rule to be tested.

        Allows addition of another rule to the list of rules that will
        be tested.  Returns the OrCheck object for convenience.
        """

        self.rules.append(rule)
        return self

    def pop_check(self):
        """Pops the last check from the list and returns them

        :returns: self, the popped check
        :rtype: :class:`.OrCheck`, class:`.Check`
        """

        check = self.rules.pop()
        return self, check


def register(name, func=None):
    # Perform the actual decoration by registering the function or
    # class.  Returns the function or class for compliance with the
    # decorator interface.
    def decorator(func):
        registered_checks[name] = func
        return func

    # If the function or class is given, do the registration
    if func:
        return decorator(func)

    return decorator


@register('rule')
class RuleCheck(Check):
    def __call__(self, target, creds, enforcer, current_rule=None):
        try:
            return _check(
                rule=enforcer.rules[self.match],
                target=target,
                creds=creds,
                enforcer=enforcer,
                current_rule=current_rule,
            )
        except KeyError:
            # We don't have any matching rule; fail closed
            return False


@register('role')
class RoleCheck(Check):
    """Check that there is a matching role in the ``creds`` dict."""

    def __call__(self, target, creds, enforcer, current_rule=None):
        try:
            match = self.match % target
        except KeyError:
            # While doing RoleCheck if key not
            # present in Target return false
            return False
        if 'roles' in creds:
            return match.lower() in [x.lower() for x in creds['roles']]
        return False


@register(None)
class GenericCheck(Check):
    """Check an individual match.

    Matches look like:

        - tenant:%(tenant_id)s
        - role:compute:admin
        - True:%(user.enabled)s
        - 'Member':%(role.name)s
    """

    def _find_in_dict(self, test_value, path_segments, match):
        '''Searches for a match in the dictionary.

        test_value is a reference inside the dictionary. Since the process is
        recursive, each call to _find_in_dict will be one level deeper.

        path_segments is the segments of the path to search.  The recursion
        ends when there are no more segments of path.

        When specifying a value inside a list, each element of the list is
        checked for a match. If the value is found within any of the sub lists
        the check succeeds; The check only fails if the entry is not in any of
        the sublists.

        '''

        if len(path_segments) == 0:
            return match == six.text_type(test_value)
        key, path_segments = path_segments[0], path_segments[1:]
        try:
            test_value = test_value[key]
        except KeyError:
            return False
        if isinstance(test_value, list):
            for val in test_value:
                if self._find_in_dict(val, path_segments, match):
                    return True
            return False
        else:
            return self._find_in_dict(test_value, path_segments, match)

    def __call__(self, target, creds, enforcer, current_rule=None):

        try:
            match = self.match % target
        except KeyError:
            # While doing GenericCheck if key not
            # present in Target return false
            return False
        try:
            # Try to interpret self.kind as a literal
            test_value = ast.literal_eval(self.kind)
            return match == six.text_type(test_value)

        except ValueError:
            pass

        path_segments = self.kind.split('.')
        return self._find_in_dict(creds, path_segments, match)
