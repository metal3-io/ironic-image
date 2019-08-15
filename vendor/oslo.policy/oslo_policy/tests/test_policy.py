# Copyright (c) 2012 OpenStack Foundation.
# All Rights Reserved.

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

"""Test of Policy Engine"""

import os

import mock
from oslo_config import cfg
from oslo_context import context
from oslo_serialization import jsonutils
from oslotest import base as test_base
import six

from oslo_policy import _cache_handler
from oslo_policy import _checks
from oslo_policy import _parser
from oslo_policy import policy
from oslo_policy.tests import base


POLICY_A_CONTENTS = jsonutils.dumps({"default": "role:fakeA"})
POLICY_B_CONTENTS = jsonutils.dumps({"default": "role:fakeB"})
POLICY_FAKE_CONTENTS = jsonutils.dumps({"default": "role:fakeC"})
POLICY_JSON_CONTENTS = jsonutils.dumps({
    "default": "rule:admin",
    "admin": "is_admin:True"
})


@_checks.register('field')
class FieldCheck(_checks.Check):
    """A non reversible check.

    All oslo.policy defined checks have a __str__ method with the property that
    rule == str(_parser.parse_rule(rule)). Consumers of oslo.policy may have
    defined checks for which that does not hold true. This FieldCheck is not
    reversible so we can use it for testing to ensure that this type of check
    does not break anything.
    """
    def __init__(self, kind, match):
        # Process the match
        resource, field_value = match.split(':', 1)
        field, value = field_value.split('=', 1)
        super(FieldCheck, self).__init__(kind, '%s:%s:%s' %
                                         (resource, field, value))
        self.field = field
        self.value = value

    def __call__(self, target_dict, cred_dict, enforcer):
        return True


class MyException(Exception):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class RulesTestCase(test_base.BaseTestCase):

    def test_init_basic(self):
        rules = policy.Rules()

        self.assertEqual({}, rules)
        self.assertIsNone(rules.default_rule)

    def test_init(self):
        rules = policy.Rules(dict(a=1, b=2, c=3), 'a')

        self.assertEqual(dict(a=1, b=2, c=3), rules)
        self.assertEqual('a', rules.default_rule)

    def test_no_default(self):
        rules = policy.Rules(dict(a=1, b=2, c=3))

        self.assertRaises(KeyError, lambda: rules['d'])

    def test_missing_default(self):
        rules = policy.Rules(dict(a=1, c=3), 'b')

        self.assertRaises(KeyError, lambda: rules['d'])

    def test_with_default(self):
        rules = policy.Rules(dict(a=1, b=2, c=3), 'b')

        self.assertEqual(2, rules['d'])

    def test_retrieval(self):
        rules = policy.Rules(dict(a=1, b=2, c=3), 'b')

        self.assertEqual(1, rules['a'])
        self.assertEqual(2, rules['b'])
        self.assertEqual(3, rules['c'])

    @mock.patch.object(_parser, 'parse_rule', lambda x: x)
    def test_load_json(self):
        exemplar = jsonutils.dumps({
            "admin_or_owner": [["role:admin"], ["project_id:%(project_id)s"]],
            "default": []
        })
        rules = policy.Rules.load(exemplar, 'default')

        self.assertEqual('default', rules.default_rule)
        self.assertEqual(dict(
            admin_or_owner=[['role:admin'], ['project_id:%(project_id)s']],
            default=[],
        ), rules)

    @mock.patch.object(_parser, 'parse_rule', lambda x: x)
    def test_load_json_invalid_exc(self):
        # When the JSON isn't valid, ValueError is raised on load.
        exemplar = """{
    "admin_or_owner": [["role:admin"], ["project_id:%(project_id)s"]],
    "default": [
}"""
        self.assertRaises(ValueError, policy.Rules.load, exemplar,
                          'default')

        # However, since change I43782d245d7652ba69613b26fe598ac79ec19929,
        # policy.Rules.load() first tries loading with the really fast
        # jsonutils.loads(), and if that fails, it tries loading with
        # yaml.safe_load().  Since YAML is a superset of JSON, some strictly
        # invalid JSON can be parsed correctly by policy.Rules.load() without
        # raising an exception.  But that means that since 1.17.0, we've been
        # accepting (strictly speaking) illegal JSON policy files, and for
        # backward compatibility, we should continue to do so.  Thus the
        # following are here to prevent regressions:

        # JSON requires double quotes, but the YAML parser doesn't care
        bad_but_acceptable = """{
    'admin_or_owner': [["role:admin"], ["project_id:%(project_id)s"]],
    'default': []
}"""
        self.assertTrue(policy.Rules.load(bad_but_acceptable, 'default'))

        # JSON does not allow bare keys, but the YAML parser doesn't care
        bad_but_acceptable = """{
    admin_or_owner: [["role:admin"], ["project_id:%(project_id)s"]],
    default: []
}"""
        self.assertTrue(policy.Rules.load(bad_but_acceptable, 'default'))

        # JSON is picky about commas, but the YAML parser is more forgiving
        # (Note the trailing , in the exemplar is invalid JSON.)
        bad_but_acceptable = """{
    admin_or_owner: [["role:admin"], ["project_id:%(project_id)s"]],
    default: [],
}"""
        self.assertTrue(policy.Rules.load(bad_but_acceptable, 'default'))

    @mock.patch.object(_parser, 'parse_rule', lambda x: x)
    def test_load_empty_data(self):
        result = policy.Rules.load('', 'default')
        self.assertEqual(result, {})

    @mock.patch.object(_parser, 'parse_rule', lambda x: x)
    def test_load_yaml(self):
        # Test that simplified YAML can be used with load().
        # Show that YAML allows useful comments.
        exemplar = """
# Define a custom rule.
admin_or_owner: role:admin or project_id:%(project_id)s
# The default rule is used when there's no action defined.
default: []
"""
        rules = policy.Rules.load(exemplar, 'default')

        self.assertEqual('default', rules.default_rule)
        self.assertEqual(dict(
            admin_or_owner='role:admin or project_id:%(project_id)s',
            default=[],
        ), rules)

    @mock.patch.object(_parser, 'parse_rule', lambda x: x)
    def test_load_yaml_invalid_exc(self):
        # When the JSON is seriously invalid, ValueError is raised on load().
        # (See test_load_json_invalid_exc for what 'seriously invalid' means.)
        exemplar = """{
# Define a custom rule.
admin_or_owner: role:admin or project_id:%(project_id)s
# The default rule is used when there's no action defined.
default: [
}"""
        self.assertRaises(ValueError, policy.Rules.load, exemplar,
                          'default')

    @mock.patch.object(_parser, 'parse_rule', lambda x: x)
    def test_from_dict(self):
        expected = {'admin_or_owner': 'role:admin', 'default': '@'}
        rules = policy.Rules.from_dict(expected, 'default')

        self.assertEqual('default', rules.default_rule)
        self.assertEqual(expected, rules)

    def test_str(self):
        exemplar = jsonutils.dumps({
            "admin_or_owner": "role:admin or project_id:%(project_id)s"
        }, indent=4)
        rules = policy.Rules(dict(
            admin_or_owner='role:admin or project_id:%(project_id)s',
        ))

        self.assertEqual(exemplar, str(rules))

    def test_str_true(self):
        exemplar = jsonutils.dumps({
            "admin_or_owner": ""
        }, indent=4)
        rules = policy.Rules(dict(
            admin_or_owner=_checks.TrueCheck(),
        ))

        self.assertEqual(exemplar, str(rules))

    def test_load_json_deprecated(self):
        with self.assertWarnsRegex(DeprecationWarning,
                                   r'load_json\(\).*load\(\)'):
            policy.Rules.load_json(jsonutils.dumps({'default': ''}, 'default'))


class EnforcerTest(base.PolicyBaseTestCase):

    def setUp(self):
        super(EnforcerTest, self).setUp()
        self.create_config_file('policy.json', POLICY_JSON_CONTENTS)

    def check_loaded_files(self, filenames):
        self.assertEqual(
            [self.get_config_file_fullname(n)
             for n in filenames],
            self.enforcer._loaded_files
        )

    def _test_scenario_with_opts_registered(self, scenario, *args, **kwargs):
        # This test registers some rules, calls the scenario and then checks
        # the registered rules. The scenario should be a method which loads
        # policy files containing POLICY_*_CONTENTS defined above. They should
        # be loaded on the self.enforcer object.

        # This should be overridden by the policy file
        self.enforcer.register_default(policy.RuleDefault(name='admin',
                                       check_str='is_admin:False'))
        # This is not in the policy file, only registered
        self.enforcer.register_default(policy.RuleDefault(name='owner',
                                       check_str='role:owner'))

        scenario(*args, **kwargs)

        self.assertIn('owner', self.enforcer.rules)
        self.assertEqual('role:owner', str(self.enforcer.rules['owner']))
        self.assertEqual('is_admin:True', str(self.enforcer.rules['admin']))
        self.assertIn('owner', self.enforcer.registered_rules)
        self.assertIn('admin', self.enforcer.registered_rules)
        self.assertNotIn('default', self.enforcer.registered_rules)
        self.assertNotIn('owner', self.enforcer.file_rules)
        self.assertIn('admin', self.enforcer.file_rules)
        self.assertIn('default', self.enforcer.file_rules)

    def test_load_file(self):
        self.conf.set_override('policy_dirs', [], group='oslo_policy')
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        self.assertIn('default', self.enforcer.rules)
        self.assertIn('admin', self.enforcer.rules)
        self.assertEqual('is_admin:True', str(self.enforcer.rules['admin']))

    def test_load_file_opts_registered(self):
        self._test_scenario_with_opts_registered(self.test_load_file)

    def test_load_directory(self):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.create_config_file(
            os.path.join('policy.d', 'b.conf'), POLICY_B_CONTENTS)
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertEqual('role:fakeB', loaded_rules['default'])
        self.assertEqual('is_admin:True', loaded_rules['admin'])
        self.check_loaded_files([
            'policy.json',
            os.path.join('policy.d', 'a.conf'),
            os.path.join('policy.d', 'b.conf'),
        ])

    def test_load_directory_opts_registered(self):
        self._test_scenario_with_opts_registered(self.test_load_directory)

    def test_load_directory_caching_with_files_updated(self):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)

        self.enforcer.load_rules(False)
        self.assertIsNotNone(self.enforcer.rules)

        old = six.next(six.itervalues(
            self.enforcer._policy_dir_mtimes))
        self.assertEqual(1, len(self.enforcer._policy_dir_mtimes))

        # Touch the file
        conf_path = os.path.join(self.config_dir, os.path.join(
            'policy.d', 'a.conf'))
        stinfo = os.stat(conf_path)
        os.utime(conf_path, (stinfo.st_atime + 10, stinfo.st_mtime + 10))

        self.enforcer.load_rules(False)
        self.assertEqual(1, len(self.enforcer._policy_dir_mtimes))
        self.assertEqual(old, six.next(six.itervalues(
            self.enforcer._policy_dir_mtimes)))

        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertEqual('is_admin:True', loaded_rules['admin'])
        self.check_loaded_files([
            'policy.json',
            os.path.join('policy.d', 'a.conf'),
            os.path.join('policy.d', 'a.conf'),
        ])

    def test_load_directory_caching_with_files_updated_opts_registered(self):
        self._test_scenario_with_opts_registered(
            self.test_load_directory_caching_with_files_updated)

    def test_load_directory_caching_with_files_same(self, overwrite=True):
        self.enforcer.overwrite = overwrite

        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)

        self.enforcer.load_rules(False)
        self.assertIsNotNone(self.enforcer.rules)

        old = six.next(six.itervalues(
            self.enforcer._policy_dir_mtimes))
        self.assertEqual(1, len(self.enforcer._policy_dir_mtimes))

        self.enforcer.load_rules(False)
        self.assertEqual(1, len(self.enforcer._policy_dir_mtimes))
        self.assertEqual(old, six.next(six.itervalues(
            self.enforcer._policy_dir_mtimes)))

        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertEqual('is_admin:True', loaded_rules['admin'])
        self.check_loaded_files([
            'policy.json',
            os.path.join('policy.d', 'a.conf'),
        ])

    def test_load_directory_caching_with_files_same_but_overwrite_false(self):
        self.test_load_directory_caching_with_files_same(overwrite=False)

    def test_load_directory_caching_with_files_same_opts_registered(self):
        self._test_scenario_with_opts_registered(
            self.test_load_directory_caching_with_files_same)

    def test_load_dir_caching_with_files_same_overwrite_false_opts_reg(self):
        # Very long test name makes this difficult
        test = getattr(self,
            'test_load_directory_caching_with_files_same_but_overwrite_false')  # NOQA
        self._test_scenario_with_opts_registered(test)

    def test_load_multiple_directories(self):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.create_config_file(
            os.path.join('policy.d', 'b.conf'), POLICY_B_CONTENTS)
        self.create_config_file(
            os.path.join('policy.2.d', 'fake.conf'), POLICY_FAKE_CONTENTS)
        self.conf.set_override('policy_dirs',
                               ['policy.d', 'policy.2.d'],
                               group='oslo_policy')
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertEqual('role:fakeC', loaded_rules['default'])
        self.assertEqual('is_admin:True', loaded_rules['admin'])
        self.check_loaded_files([
            'policy.json',
            os.path.join('policy.d', 'a.conf'),
            os.path.join('policy.d', 'b.conf'),
            os.path.join('policy.2.d', 'fake.conf'),
        ])

    def test_load_multiple_directories_opts_registered(self):
        self._test_scenario_with_opts_registered(
            self.test_load_multiple_directories)

    def test_load_non_existed_directory(self):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.conf.set_override('policy_dirs',
                               ['policy.d', 'policy.x.d'],
                               group='oslo_policy')
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        self.assertIn('default', self.enforcer.rules)
        self.assertIn('admin', self.enforcer.rules)
        self.check_loaded_files(
            ['policy.json', os.path.join('policy.d', 'a.conf')])

    def test_load_non_existed_directory_opts_registered(self):
        self._test_scenario_with_opts_registered(
            self.test_load_non_existed_directory)

    def test_load_policy_dirs_with_non_directory(self):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.conf.set_override('policy_dirs',
                               [os.path.join('policy.d', 'a.conf')],
                               group='oslo_policy')
        self.assertRaises(ValueError, self.enforcer.load_rules, True)

    @mock.patch('oslo_policy.policy.Enforcer.check_rules')
    def test_load_rules_twice(self, mock_check_rules):
        self.enforcer.load_rules()
        self.enforcer.load_rules()
        self.assertEqual(1, mock_check_rules.call_count)

    @mock.patch('oslo_policy.policy.Enforcer.check_rules')
    def test_load_rules_twice_force(self, mock_check_rules):
        self.enforcer.load_rules(True)
        self.enforcer.load_rules(True)
        self.assertEqual(2, mock_check_rules.call_count)

    @mock.patch('oslo_policy.policy.Enforcer.check_rules')
    def test_load_rules_twice_clear(self, mock_check_rules):
        self.enforcer.load_rules()
        self.enforcer.clear()
        # NOTE(bnemec): It's weird that we have to pass True here, but clear
        # sets enforcer.use_conf to False, which causes load_rules to be a
        # noop when called with no parameters.  This is probably a bug.
        self.enforcer.load_rules(True)
        self.assertEqual(2, mock_check_rules.call_count)

    @mock.patch('oslo_policy.policy.Enforcer.check_rules')
    def test_load_directory_twice(self, mock_check_rules):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.create_config_file(
            os.path.join('policy.d', 'b.conf'), POLICY_B_CONTENTS)
        self.enforcer.load_rules()
        self.enforcer.load_rules()
        self.assertEqual(1, mock_check_rules.call_count)
        self.assertIsNotNone(self.enforcer.rules)

    @mock.patch('oslo_policy.policy.Enforcer.check_rules')
    def test_load_directory_twice_force(self, mock_check_rules):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.create_config_file(
            os.path.join('policy.d', 'b.conf'), POLICY_B_CONTENTS)
        self.enforcer.load_rules(True)
        self.enforcer.load_rules(True)
        self.assertEqual(2, mock_check_rules.call_count)
        self.assertIsNotNone(self.enforcer.rules)

    @mock.patch('oslo_policy.policy.Enforcer.check_rules')
    def test_load_directory_twice_changed(self, mock_check_rules):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.enforcer.load_rules()

        # Touch the file
        conf_path = os.path.join(self.config_dir, os.path.join(
            'policy.d', 'a.conf'))
        stinfo = os.stat(conf_path)
        os.utime(conf_path, (stinfo.st_atime + 10, stinfo.st_mtime + 10))

        self.enforcer.load_rules()
        self.assertEqual(2, mock_check_rules.call_count)
        self.assertIsNotNone(self.enforcer.rules)

    def test_set_rules_type(self):
        self.assertRaises(TypeError,
                          self.enforcer.set_rules,
                          'dummy')

    @mock.patch.object(_cache_handler, 'delete_cached_file', mock.Mock())
    def test_clear(self):
        # Make sure the rules are reset
        self.enforcer.rules = 'spam'
        self.enforcer.clear()
        self.assertEqual({}, self.enforcer.rules)
        self.assertIsNone(self.enforcer.default_rule)
        self.assertIsNone(self.enforcer.policy_path)

    def test_clear_opts_registered(self):
        # This should be overridden by the policy file
        self.enforcer.register_default(policy.RuleDefault(name='admin',
                                       check_str='is_admin:False'))
        # This is not in the policy file, only registered
        self.enforcer.register_default(policy.RuleDefault(name='owner',
                                       check_str='role:owner'))

        self.test_clear()
        self.assertEqual({}, self.enforcer.registered_rules)

    def test_rule_with_check(self):
        rules_json = jsonutils.dumps({
            "deny_stack_user": "not role:stack_user",
            "cloudwatch:PutMetricData": ""
        })
        rules = policy.Rules.load(rules_json)
        self.enforcer.set_rules(rules)
        action = 'cloudwatch:PutMetricData'
        creds = {'roles': ''}
        self.assertTrue(self.enforcer.enforce(action, {}, creds))

    def test_enforcer_with_default_rule(self):
        rules_json = jsonutils.dumps({
            "deny_stack_user": "not role:stack_user",
            "cloudwatch:PutMetricData": ""
        })
        rules = policy.Rules.load(rules_json)
        default_rule = _checks.TrueCheck()
        enforcer = policy.Enforcer(self.conf, default_rule=default_rule)
        enforcer.set_rules(rules)
        action = 'cloudwatch:PutMetricData'
        creds = {'roles': ''}
        self.assertTrue(enforcer.enforce(action, {}, creds))

    def test_enforcer_force_reload_with_overwrite(self, opts_registered=0):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.create_config_file(
            os.path.join('policy.d', 'b.conf'), POLICY_B_CONTENTS)

        # Prepare in memory fake policies.
        self.enforcer.set_rules({'test': _parser.parse_rule('role:test')},
                                use_conf=True)
        self.enforcer.set_rules({'default': _parser.parse_rule('role:fakeZ')},
                                overwrite=False,  # Keeps 'test' role.
                                use_conf=True)

        self.enforcer.overwrite = True

        # Call enforce(), it will load rules from
        # policy configuration files, to overwrite
        # existing fake ones.
        self.assertFalse(self.enforcer.enforce('test', {},
                                               {'roles': ['test']}))
        self.assertTrue(self.enforcer.enforce('default', {},
                                              {'roles': ['fakeB']}))

        # Check against rule dict again from
        # enforcer object directly.
        self.assertNotIn('test', self.enforcer.rules)
        self.assertIn('default', self.enforcer.rules)
        self.assertIn('admin', self.enforcer.rules)
        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertEqual(2 + opts_registered, len(loaded_rules))
        self.assertIn('role:fakeB', loaded_rules['default'])
        self.assertIn('is_admin:True', loaded_rules['admin'])

    def test_enforcer_force_reload_with_overwrite_opts_registered(self):
        self._test_scenario_with_opts_registered(
            self.test_enforcer_force_reload_with_overwrite, opts_registered=1)

    def test_enforcer_force_reload_without_overwrite(self, opts_registered=0):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.create_config_file(
            os.path.join('policy.d', 'b.conf'), POLICY_B_CONTENTS)

        # Prepare in memory fake policies.
        self.enforcer.set_rules({'test': _parser.parse_rule('role:test')},
                                use_conf=True)
        self.enforcer.set_rules({'default': _parser.parse_rule('role:fakeZ')},
                                overwrite=False,  # Keeps 'test' role.
                                use_conf=True)

        self.enforcer.overwrite = False
        self.enforcer._is_directory_updated = lambda x, y: True

        # Call enforce(), it will load rules from
        # policy configuration files, to merge with
        # existing fake ones.
        self.assertTrue(self.enforcer.enforce('test', {},
                                              {'roles': ['test']}))
        # The existing rules have a same key with
        # new loaded ones will be overwrote.
        self.assertFalse(self.enforcer.enforce('default', {},
                                               {'roles': ['fakeZ']}))

        # Check against rule dict again from
        # enforcer object directly.
        self.assertIn('test', self.enforcer.rules)
        self.assertIn('default', self.enforcer.rules)
        self.assertIn('admin', self.enforcer.rules)
        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertEqual(3 + opts_registered, len(loaded_rules))
        self.assertIn('role:test', loaded_rules['test'])
        self.assertIn('role:fakeB', loaded_rules['default'])
        self.assertIn('is_admin:True', loaded_rules['admin'])

    def test_enforcer_force_reload_without_overwrite_opts_registered(self):
        self._test_scenario_with_opts_registered(
            self.test_enforcer_force_reload_without_overwrite,
            opts_registered=1)

    def test_enforcer_keep_use_conf_flag_after_reload(self):
        self.create_config_file(
            os.path.join('policy.d', 'a.conf'), POLICY_A_CONTENTS)
        self.create_config_file(
            os.path.join('policy.d', 'b.conf'), POLICY_B_CONTENTS)

        self.assertTrue(self.enforcer.use_conf)
        self.assertTrue(self.enforcer.enforce('default', {},
                                              {'roles': ['fakeB']}))
        self.assertFalse(self.enforcer.enforce('test', {},
                                               {'roles': ['test']}))
        # After enforcement the flag should
        # be remained there.
        self.assertTrue(self.enforcer.use_conf)
        self.assertFalse(self.enforcer.enforce('_dynamic_test_rule', {},
                                               {'roles': ['test']}))
        # Then if configure file got changed,
        # reloading will be triggered when calling
        # enforcer(), this case could happen only
        # when use_conf flag equals True.
        rules = jsonutils.loads(str(self.enforcer.rules))
        rules['_dynamic_test_rule'] = 'role:test'

        with open(self.enforcer.policy_path, 'w') as f:
            f.write(jsonutils.dumps(rules))

        self.enforcer.load_rules(force_reload=True)
        self.assertTrue(self.enforcer.enforce('_dynamic_test_rule', {},
                                              {'roles': ['test']}))

    def test_enforcer_keep_use_conf_flag_after_reload_opts_registered(self):
        # This test does not use _test_scenario_with_opts_registered because
        # it loads all rules and then dumps them to a policy file and reloads.
        # That breaks the ability to differentiate between registered and file
        # loaded policies.

        # This should be overridden by the policy file
        self.enforcer.register_default(policy.RuleDefault(name='admin',
                                       check_str='is_admin:False'))
        # This is not in the policy file, only registered
        self.enforcer.register_default(policy.RuleDefault(name='owner',
                                       check_str='role:owner'))

        self.test_enforcer_keep_use_conf_flag_after_reload()

        self.assertIn('owner', self.enforcer.rules)
        self.assertEqual('role:owner', str(self.enforcer.rules['owner']))
        self.assertEqual('is_admin:True', str(self.enforcer.rules['admin']))

    def test_enforcer_force_reload_false(self):
        self.enforcer.set_rules({'test': 'test'})
        self.enforcer.load_rules(force_reload=False)
        self.assertIn('test', self.enforcer.rules)
        self.assertNotIn('default', self.enforcer.rules)
        self.assertNotIn('admin', self.enforcer.rules)

    def test_enforcer_overwrite_rules(self):
        self.enforcer.set_rules({'test': 'test'})
        self.enforcer.set_rules({'test': 'test1'}, overwrite=True)
        self.assertEqual({'test': 'test1'}, self.enforcer.rules)

    def test_enforcer_update_rules(self):
        self.enforcer.set_rules({'test': 'test'})
        self.enforcer.set_rules({'test1': 'test1'}, overwrite=False)
        self.assertEqual({'test': 'test', 'test1': 'test1'},
                         self.enforcer.rules)

    def test_enforcer_with_default_policy_file(self):
        enforcer = policy.Enforcer(self.conf)
        self.assertEqual(self.conf.oslo_policy.policy_file,
                         enforcer.policy_file)

    def test_enforcer_with_policy_file(self):
        enforcer = policy.Enforcer(self.conf, policy_file='non-default.json')
        self.assertEqual('non-default.json', enforcer.policy_file)

    def test_get_policy_path_raises_exc(self):
        enforcer = policy.Enforcer(self.conf, policy_file='raise_error.json')
        e = self.assertRaises(cfg.ConfigFilesNotFoundError,
                              enforcer._get_policy_path, enforcer.policy_file)
        self.assertEqual(('raise_error.json', ), e.config_files)

    def test_enforcer_set_rules(self):
        self.enforcer.load_rules()
        self.enforcer.set_rules({'test': 'test1'})
        self.enforcer.load_rules()
        self.assertEqual({'test': 'test1'}, self.enforcer.rules)

    def test_enforcer_default_rule_name(self):
        enforcer = policy.Enforcer(self.conf, default_rule='foo_rule')
        self.assertEqual('foo_rule', enforcer.rules.default_rule)
        self.conf.set_override('policy_default_rule', 'bar_rule',
                               group='oslo_policy')
        enforcer = policy.Enforcer(self.conf, default_rule='foo_rule')
        self.assertEqual('foo_rule', enforcer.rules.default_rule)
        enforcer = policy.Enforcer(self.conf, )
        self.assertEqual('bar_rule', enforcer.rules.default_rule)

    def test_enforcer_register_twice_raises(self):
        self.enforcer.register_default(policy.RuleDefault(name='owner',
                                       check_str='role:owner'))
        self.assertRaises(policy.DuplicatePolicyError,
                          self.enforcer.register_default,
                          policy.RuleDefault(name='owner',
                                             check_str='role:owner'))

    def test_non_reversible_check(self):
        self.create_config_file('policy.json',
                                jsonutils.dumps(
                                    {'shared': 'field:networks:shared=True'}))
        # load_rules succeeding without error is the focus of this test
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertNotEqual('field:networks:shared=True',
                            loaded_rules['shared'])

    def test_authorize_opt_registered(self):
        self.enforcer.register_default(policy.RuleDefault(name='test',
                                       check_str='role:test'))
        self.assertTrue(self.enforcer.authorize('test', {},
                                                {'roles': ['test']}))

    def test_authorize_opt_not_registered(self):
        self.assertRaises(policy.PolicyNotRegistered,
                          self.enforcer.authorize, 'test', {},
                          {'roles': ['test']})

    def test_enforcer_accepts_context_objects(self):
        rule = policy.RuleDefault(name='fake_rule', check_str='role:test')
        self.enforcer.register_default(rule)

        request_context = context.RequestContext()
        target_dict = {}
        self.enforcer.enforce('fake_rule', target_dict, request_context)

    def test_enforcer_accepts_subclassed_context_objects(self):
        rule = policy.RuleDefault(name='fake_rule', check_str='role:test')
        self.enforcer.register_default(rule)

        class SpecializedContext(context.RequestContext):
            pass

        request_context = SpecializedContext()
        target_dict = {}
        self.enforcer.enforce('fake_rule', target_dict, request_context)

    def test_enforcer_rejects_non_context_objects(self):
        rule = policy.RuleDefault(name='fake_rule', check_str='role:test')
        self.enforcer.register_default(rule)

        class InvalidContext(object):
            pass

        request_context = InvalidContext()
        target_dict = {}
        self.assertRaises(
            policy.InvalidContextObject, self.enforcer.enforce, 'fake_rule',
            target_dict, request_context
        )

    @mock.patch.object(policy.Enforcer, '_map_context_attributes_into_creds')
    def test_enforcer_call_map_context_attributes(self, map_mock):
        map_mock.return_value = {}
        rule = policy.RuleDefault(name='fake_rule', check_str='role:test')
        self.enforcer.register_default(rule)

        request_context = context.RequestContext()
        target_dict = {}
        self.enforcer.enforce('fake_rule', target_dict, request_context)
        map_mock.assert_called_once_with(request_context)

    def test_enforcer_consolidates_context_attributes_with_creds(self):
        request_context = context.RequestContext()
        expected_creds = request_context.to_policy_values()

        creds = self.enforcer._map_context_attributes_into_creds(
            request_context
        )

        # We don't use self.assertDictEqual here because to_policy_values
        # actaully returns a non-dict object that just behaves like a
        # dictionary, but does some special handling when people access
        # deprecated policy values.
        for k, v in expected_creds.items():
            self.assertEqual(expected_creds[k], creds[k])

    def test_map_context_attributes_populated_system(self):
        request_context = context.RequestContext(system_scope='all')
        expected_creds = request_context.to_policy_values()
        expected_creds['system'] = 'all'

        creds = self.enforcer._map_context_attributes_into_creds(
            request_context
        )

        # We don't use self.assertDictEqual here because to_policy_values
        # actaully returns a non-dict object that just behaves like a
        # dictionary, but does some special handling when people access
        # deprecated policy values.
        for k, v in expected_creds.items():
            self.assertEqual(expected_creds[k], creds[k])

    def test_enforcer_accepts_policy_values_from_context(self):
        rule = policy.RuleDefault(name='fake_rule', check_str='role:test')
        self.enforcer.register_default(rule)

        request_context = context.RequestContext()
        policy_values = request_context.to_policy_values()
        target_dict = {}
        self.enforcer.enforce('fake_rule', target_dict, policy_values)

    def test_enforcer_understands_system_scope(self):
        self.conf.set_override('enforce_scope', True, group='oslo_policy')
        rule = policy.RuleDefault(
            name='fake_rule', check_str='role:test', scope_types=['system']
        )
        self.enforcer.register_default(rule)

        ctx = context.RequestContext(system_scope='all')
        target_dict = {}
        self.enforcer.enforce('fake_rule', target_dict, ctx)

    def test_enforcer_raises_invalid_scope_with_system_scope_type(self):
        self.conf.set_override('enforce_scope', True, group='oslo_policy')
        rule = policy.RuleDefault(
            name='fake_rule', check_str='role:test', scope_types=['system']
        )
        self.enforcer.register_default(rule)

        # model a domain-scoped token, which should fail enforcement
        ctx = context.RequestContext(domain_id='fake')
        target_dict = {}
        self.assertRaises(
            policy.InvalidScope, self.enforcer.enforce, 'fake_rule',
            target_dict, ctx
        )

        # model a project-scoped token, which should fail enforcement
        ctx = context.RequestContext(project_id='fake')
        self.assertRaises(
            policy.InvalidScope, self.enforcer.enforce, 'fake_rule',
            target_dict, ctx
        )

    def test_enforcer_understands_domain_scope(self):
        self.conf.set_override('enforce_scope', True, group='oslo_policy')
        rule = policy.RuleDefault(
            name='fake_rule', check_str='role:test', scope_types=['domain']
        )
        self.enforcer.register_default(rule)

        ctx = context.RequestContext(domain_id='fake')
        target_dict = {}
        self.enforcer.enforce('fake_rule', target_dict, ctx)

    def test_enforcer_raises_invalid_scope_with_domain_scope_type(self):
        self.conf.set_override('enforce_scope', True, group='oslo_policy')
        rule = policy.RuleDefault(
            name='fake_rule', check_str='role:test', scope_types=['domain']
        )
        self.enforcer.register_default(rule)

        # model a system-scoped token, which should fail enforcement
        ctx = context.RequestContext(system_scope='all')
        target_dict = {}
        self.assertRaises(
            policy.InvalidScope, self.enforcer.enforce, 'fake_rule',
            target_dict, ctx
        )

        # model a project-scoped token, which should fail enforcement
        ctx = context.RequestContext(project_id='fake')
        self.assertRaises(
            policy.InvalidScope, self.enforcer.enforce, 'fake_rule',
            target_dict, ctx
        )

    def test_enforcer_understands_project_scope(self):
        self.conf.set_override('enforce_scope', True, group='oslo_policy')
        rule = policy.RuleDefault(
            name='fake_rule', check_str='role:test', scope_types=['project']
        )
        self.enforcer.register_default(rule)

        ctx = context.RequestContext(project_id='fake')
        target_dict = {}
        self.enforcer.enforce('fake_rule', target_dict, ctx)

    def test_enforcer_raises_invalid_scope_with_project_scope_type(self):
        self.conf.set_override('enforce_scope', True, group='oslo_policy')
        rule = policy.RuleDefault(
            name='fake_rule', check_str='role:test', scope_types=['project']
        )
        self.enforcer.register_default(rule)

        # model a system-scoped token, which should fail enforcement
        ctx = context.RequestContext(system_scope='all')
        target_dict = {}
        self.assertRaises(
            policy.InvalidScope, self.enforcer.enforce, 'fake_rule',
            target_dict, ctx
        )

        # model a domain-scoped token, which should fail enforcement
        ctx = context.RequestContext(domain_id='fake')
        self.assertRaises(
            policy.InvalidScope, self.enforcer.enforce, 'fake_rule',
            target_dict, ctx
        )


class EnforcerNoPolicyFileTest(base.PolicyBaseTestCase):
    def setUp(self):
        super(EnforcerNoPolicyFileTest, self).setUp()

    def check_loaded_files(self, filenames):
        self.assertEqual(
            [self.get_config_file_fullname(n)
             for n in filenames],
            self.enforcer._loaded_files
        )

    def test_load_rules(self):
        # Check that loading rules with no policy file does not error
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        self.assertEqual(0, len(self.enforcer.rules))

    def test_opts_registered(self):
        self.enforcer.register_default(policy.RuleDefault(name='admin',
                                       check_str='is_admin:False'))
        self.enforcer.register_default(policy.RuleDefault(name='owner',
                                       check_str='role:owner'))
        self.enforcer.load_rules(True)

        self.assertEqual({}, self.enforcer.file_rules)
        self.assertEqual('role:owner', str(self.enforcer.rules['owner']))
        self.assertEqual('is_admin:False', str(self.enforcer.rules['admin']))

    def test_load_directory(self):
        self.create_config_file('policy.d/a.conf', POLICY_JSON_CONTENTS)
        self.create_config_file('policy.d/b.conf', POLICY_B_CONTENTS)
        self.enforcer.load_rules(True)
        self.assertIsNotNone(self.enforcer.rules)
        loaded_rules = jsonutils.loads(str(self.enforcer.rules))
        self.assertEqual('role:fakeB', loaded_rules['default'])
        self.assertEqual('is_admin:True', loaded_rules['admin'])
        self.check_loaded_files([
            'policy.d/a.conf',
            'policy.d/b.conf',
        ])


class CheckFunctionTestCase(base.PolicyBaseTestCase):

    def setUp(self):
        super(CheckFunctionTestCase, self).setUp()
        self.create_config_file('policy.json', POLICY_JSON_CONTENTS)

    def test_check_explicit(self):
        rule = base.FakeCheck()
        creds = {}
        result = self.enforcer.enforce(rule, 'target', creds)
        self.assertEqual(('target', creds, self.enforcer), result)

    def test_check_no_rules(self):
        # Clear the policy.json file created in setUp()
        self.create_config_file('policy.json', "{}")
        self.enforcer.default_rule = None
        self.enforcer.load_rules()
        creds = {}
        result = self.enforcer.enforce('rule', 'target', creds)
        self.assertFalse(result)

    def test_check_with_rule(self):
        self.enforcer.set_rules(dict(default=base.FakeCheck()))
        creds = {}
        result = self.enforcer.enforce('default', 'target', creds)

        self.assertEqual(('target', creds, self.enforcer), result)

    def test_check_rule_not_exist_not_empty_policy_file(self):
        # If the rule doesn't exist, then enforce() fails rather than KeyError.

        # This test needs a non-empty file otherwise the code short-circuits.
        self.create_config_file('policy.json', jsonutils.dumps({"a_rule": []}))
        self.enforcer.default_rule = None
        self.enforcer.load_rules()
        creds = {}
        result = self.enforcer.enforce('rule', 'target', creds)
        self.assertFalse(result)

    def test_check_raise_default(self):
        # When do_raise=True and exc is not used then PolicyNotAuthorized is
        # raised.
        self.enforcer.set_rules(dict(default=_checks.FalseCheck()))

        creds = {}
        self.assertRaisesRegex(policy.PolicyNotAuthorized,
                               " is disallowed by policy",
                               self.enforcer.enforce,
                               'rule', 'target', creds, True)

    def test_check_raise_custom_exception(self):
        self.enforcer.set_rules(dict(default=_checks.FalseCheck()))

        creds = {}
        exc = self.assertRaises(
            MyException, self.enforcer.enforce, 'rule', 'target', creds,
            True, MyException, 'arg1', 'arg2', kw1='kwarg1',
            kw2='kwarg2')
        self.assertEqual(('arg1', 'arg2'), exc.args)
        self.assertEqual(dict(kw1='kwarg1', kw2='kwarg2'), exc.kwargs)


class RegisterCheckTestCase(base.PolicyBaseTestCase):

    @mock.patch.object(_checks, 'registered_checks', {})
    def test_register_check(self):
        class TestCheck(policy.Check):
            pass

        policy.register('spam', TestCheck)

        self.assertEqual(dict(spam=TestCheck), _checks.registered_checks)


class BaseCheckTypesTestCase(base.PolicyBaseTestCase):

    @mock.patch.object(_checks, 'registered_checks', {})
    def test_base_check_types_are_public(self):
        '''Check that those check types are part of public API.

           They are blessed to be used by library consumers.
        '''
        for check_type in (policy.AndCheck, policy.NotCheck,
                           policy.OrCheck, policy.RuleCheck):
            class TestCheck(check_type):
                pass

            check_str = str(check_type)
            policy.register(check_str, TestCheck)
            self.assertEqual(
                TestCheck, _checks.registered_checks[check_str],
                message='%s check type is not public.' % check_str)


class RuleDefaultTestCase(base.PolicyBaseTestCase):
    def test_rule_is_parsed(self):
        opt = policy.RuleDefault(name='foo', check_str='rule:foo')
        self.assertIsInstance(opt.check, _checks.BaseCheck)
        self.assertEqual('rule:foo', str(opt.check))

    def test_str(self):
        opt = policy.RuleDefault(name='foo', check_str='rule:foo')
        self.assertEqual('"foo": "rule:foo"', str(opt))

    def test_equality_obvious(self):
        opt1 = policy.RuleDefault(name='foo', check_str='rule:foo',
                                  description='foo')
        opt2 = policy.RuleDefault(name='foo', check_str='rule:foo',
                                  description='bar')
        self.assertEqual(opt1, opt2)

    def test_equality_less_obvious(self):
        opt1 = policy.RuleDefault(name='foo', check_str='',
                                  description='foo')
        opt2 = policy.RuleDefault(name='foo', check_str='@',
                                  description='bar')
        self.assertEqual(opt1, opt2)

    def test_not_equal_check(self):
        opt1 = policy.RuleDefault(name='foo', check_str='rule:foo',
                                  description='foo')
        opt2 = policy.RuleDefault(name='foo', check_str='rule:bar',
                                  description='bar')
        self.assertNotEqual(opt1, opt2)

    def test_not_equal_name(self):
        opt1 = policy.RuleDefault(name='foo', check_str='rule:foo',
                                  description='foo')
        opt2 = policy.RuleDefault(name='bar', check_str='rule:foo',
                                  description='bar')
        self.assertNotEqual(opt1, opt2)

    def test_not_equal_class(self):
        class NotRuleDefault(object):
            def __init__(self, name, check_str):
                self.name = name
                self.check = _parser.parse_rule(check_str)

        opt1 = policy.RuleDefault(name='foo', check_str='rule:foo')
        opt2 = NotRuleDefault(name='foo', check_str='rule:foo')
        self.assertNotEqual(opt1, opt2)

    def test_equal_subclass(self):
        class RuleDefaultSub(policy.RuleDefault):
            pass

        opt1 = policy.RuleDefault(name='foo', check_str='rule:foo')
        opt2 = RuleDefaultSub(name='foo', check_str='rule:foo')
        self.assertEqual(opt1, opt2)

    def test_not_equal_subclass(self):
        class RuleDefaultSub(policy.RuleDefault):
            pass

        opt1 = policy.RuleDefault(name='foo', check_str='rule:foo')
        opt2 = RuleDefaultSub(name='bar', check_str='rule:foo')
        self.assertNotEqual(opt1, opt2)

    def test_create_opt_with_scope_types(self):
        scope_types = ['project']
        opt = policy.RuleDefault(
            name='foo',
            check_str='role:bar',
            scope_types=scope_types
        )
        self.assertEqual(opt.scope_types, scope_types)

    def test_create_opt_with_scope_type_strings_fails(self):
        self.assertRaises(
            ValueError,
            policy.RuleDefault,
            name='foo',
            check_str='role:bar',
            scope_types='project'
        )

    def test_create_opt_with_multiple_scope_types(self):
        opt = policy.RuleDefault(
            name='foo',
            check_str='role:bar',
            scope_types=['project', 'domain', 'system']
        )

        self.assertEqual(opt.scope_types, ['project', 'domain', 'system'])

    def test_ensure_scope_types_are_unique(self):
        self.assertRaises(
            ValueError,
            policy.RuleDefault,
            name='foo',
            check_str='role:bar',
            scope_types=['project', 'project']
        )


class DocumentedRuleDefaultDeprecationTestCase(base.PolicyBaseTestCase):

    def test_deprecate_a_policy_check_string(self):
        deprecated_rule = policy.DeprecatedRule(
            name='foo:create_bar',
            check_str='role:fizz'
        )

        rule_list = [policy.DocumentedRuleDefault(
            name='foo:create_bar',
            check_str='role:bang',
            description='Create a bar.',
            operations=[{'path': '/v1/bars', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason='"role:bang" is a better default',
            deprecated_since='N'
        )]
        enforcer = policy.Enforcer(self.conf)
        enforcer.register_defaults(rule_list)
        expected_msg = (
            'Policy "foo:create_bar":"role:fizz" was deprecated in N in favor '
            'of "foo:create_bar":"role:bang". Reason: "role:bang" is a better '
            'default. Either ensure your deployment is ready for the new '
            'default or copy/paste the deprecated policy into your policy '
            'file and maintain it manually.'
        )

        with mock.patch('warnings.warn') as mock_warn:
            enforcer.load_rules()
            mock_warn.assert_called_once_with(expected_msg)

    def test_deprecate_a_policy_name(self):
        deprecated_rule = policy.DeprecatedRule(
            name='foo:bar',
            check_str='role:baz'
        )

        rule_list = [policy.DocumentedRuleDefault(
            name='foo:create_bar',
            check_str='role:baz',
            description='Create a bar.',
            operations=[{'path': '/v1/bars/', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason=(
                '"foo:bar" is not granular enough. If your deployment has '
                'overridden "foo:bar", ensure you override the new policies '
                'with same role or rule. Not doing this will require the '
                'service to assume the new defaults for "foo:bar:create", '
                '"foo:bar:update", "foo:bar:list", and "foo:bar:delete", '
                'which might be backwards incompatible for your deployment'
            ),
            deprecated_since='N'
        )]
        expected_msg = (
            'Policy "foo:bar":"role:baz" was deprecated in N in favor of '
            '"foo:create_bar":"role:baz". Reason: "foo:bar" is not granular '
            'enough. If your deployment has overridden "foo:bar", ensure you '
            'override the new policies with same role or rule. Not doing this '
            'will require the service to assume the new defaults for '
            '"foo:bar:create", "foo:bar:update", "foo:bar:list", and '
            '"foo:bar:delete", which might be backwards incompatible for your '
            'deployment. Either ensure your deployment is ready for the new '
            'default or copy/paste the deprecated policy into your policy '
            'file and maintain it manually.'
        )

        rules = jsonutils.dumps({'foo:bar': 'role:bang'})
        self.create_config_file('policy.json', rules)
        enforcer = policy.Enforcer(self.conf)
        enforcer.register_defaults(rule_list)

        with mock.patch('warnings.warn') as mock_warn:
            enforcer.load_rules(True)
            mock_warn.assert_called_once_with(expected_msg)

    def test_deprecate_a_policy_for_removal_logs_warning_when_overridden(self):
        rule_list = [policy.DocumentedRuleDefault(
            name='foo:bar',
            check_str='role:baz',
            description='Create a foo.',
            operations=[{'path': '/v1/foos/', 'method': 'POST'}],
            deprecated_for_removal=True,
            deprecated_reason=(
                '"foo:bar" is no longer a policy used by the service'
            ),
            deprecated_since='N'
        )]
        expected_msg = (
            'Policy "foo:bar":"role:baz" was deprecated for removal in N. '
            'Reason: "foo:bar" is no longer a policy used by the service. Its '
            'value may be silently ignored in the future.'
        )
        rules = jsonutils.dumps({'foo:bar': 'role:bang'})
        self.create_config_file('policy.json', rules)
        enforcer = policy.Enforcer(self.conf)
        enforcer.register_defaults(rule_list)

        with mock.patch('warnings.warn') as mock_warn:
            enforcer.load_rules()
            mock_warn.assert_called_once_with(expected_msg)

    def test_deprecate_a_policy_for_removal_does_not_log_warning(self):
        # We should only log a warning for operators if they are supplying an
        # override for a policy that is deprecated for removal.
        rule_list = [policy.DocumentedRuleDefault(
            name='foo:bar',
            check_str='role:baz',
            description='Create a foo.',
            operations=[{'path': '/v1/foos/', 'method': 'POST'}],
            deprecated_for_removal=True,
            deprecated_reason=(
                '"foo:bar" is no longer a policy used by the service'
            ),
            deprecated_since='N'
        )]
        enforcer = policy.Enforcer(self.conf)
        enforcer.register_defaults(rule_list)

        with mock.patch('warnings.warn') as mock_warn:
            enforcer.load_rules()
            mock_warn.assert_not_called()

    def test_deprecate_check_str_suppress_does_not_log_warning(self):
        deprecated_rule = policy.DeprecatedRule(
            name='foo:create_bar',
            check_str='role:fizz'
        )

        rule_list = [policy.DocumentedRuleDefault(
            name='foo:create_bar',
            check_str='role:bang',
            description='Create a bar.',
            operations=[{'path': '/v1/bars', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason='"role:bang" is a better default',
            deprecated_since='N'
        )]
        enforcer = policy.Enforcer(self.conf)
        enforcer.suppress_deprecation_warnings = True
        enforcer.register_defaults(rule_list)
        with mock.patch('warnings.warn') as mock_warn:
            enforcer.load_rules()
            mock_warn.assert_not_called()

    def test_deprecate_name_suppress_does_not_log_warning(self):
        deprecated_rule = policy.DeprecatedRule(
            name='foo:bar',
            check_str='role:baz'
        )

        rule_list = [policy.DocumentedRuleDefault(
            name='foo:create_bar',
            check_str='role:baz',
            description='Create a bar.',
            operations=[{'path': '/v1/bars/', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason='"foo:bar" is not granular enough.',
            deprecated_since='N'
        )]

        rules = jsonutils.dumps({'foo:bar': 'role:bang'})
        self.create_config_file('policy.json', rules)
        enforcer = policy.Enforcer(self.conf)
        enforcer.suppress_deprecation_warnings = True
        enforcer.register_defaults(rule_list)

        with mock.patch('warnings.warn') as mock_warn:
            enforcer.load_rules()
            mock_warn.assert_not_called()

    def test_deprecate_for_removal_suppress_does_not_log_warning(self):
        rule_list = [policy.DocumentedRuleDefault(
            name='foo:bar',
            check_str='role:baz',
            description='Create a foo.',
            operations=[{'path': '/v1/foos/', 'method': 'POST'}],
            deprecated_for_removal=True,
            deprecated_reason=(
                '"foo:bar" is no longer a policy used by the service'
            ),
            deprecated_since='N'
        )]
        rules = jsonutils.dumps({'foo:bar': 'role:bang'})
        self.create_config_file('policy.json', rules)
        enforcer = policy.Enforcer(self.conf)
        enforcer.suppress_deprecation_warnings = True
        enforcer.register_defaults(rule_list)

        with mock.patch('warnings.warn') as mock_warn:
            enforcer.load_rules()
            mock_warn.assert_not_called()

    def test_deprecated_policy_for_removal_must_include_deprecated_since(self):
        self.assertRaises(
            ValueError,
            policy.DocumentedRuleDefault,
            name='foo:bar',
            check_str='rule:baz',
            description='Create a foo.',
            operations=[{'path': '/v1/foos/', 'method': 'POST'}],
            deprecated_for_removal=True,
            deprecated_reason='Some reason.'
        )

    def test_deprecated_policy_must_include_deprecated_since(self):
        deprecated_rule = policy.DeprecatedRule(
            name='foo:bar',
            check_str='rule:baz'
        )

        self.assertRaises(
            ValueError,
            policy.DocumentedRuleDefault,
            name='foo:bar',
            check_str='rule:baz',
            description='Create a foo.',
            operations=[{'path': '/v1/foos/', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason='Some reason.'
        )

    def test_deprecated_rule_requires_deprecated_rule_object(self):
        self.assertRaises(
            ValueError,
            policy.DocumentedRuleDefault,
            name='foo:bar',
            check_str='rule:baz',
            description='Create a foo.',
            operations=[{'path': '/v1/foos/', 'method': 'POST'}],
            deprecated_rule='foo:bar',
            deprecated_reason='Some reason.'
        )

    def test_deprecated_policy_must_include_deprecated_reason(self):
        self.assertRaises(
            ValueError,
            policy.DocumentedRuleDefault,
            name='foo:bar',
            check_str='rule:baz',
            description='Create a foo.',
            operations=[{'path': '/v1/foos/', 'method': 'POST'}],
            deprecated_for_removal=True,
            deprecated_since='N'
        )

    def test_override_deprecated_policy_with_old_name(self):
        # Simulate an operator overriding a policy
        rules = jsonutils.dumps({'foo:bar': 'role:bazz'})
        self.create_config_file('policy.json', rules)

        # Deprecate the policy name and check string in favor of something
        # better.
        deprecated_rule = policy.DeprecatedRule(
            name='foo:bar',
            check_str='role:fizz'
        )
        rule_list = [policy.DocumentedRuleDefault(
            name='foo:create_bar',
            check_str='role:bang',
            description='Create a bar.',
            operations=[{'path': '/v1/bars', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason='"role:bang" is a better default',
            deprecated_since='N'
        )]
        self.enforcer.register_defaults(rule_list)

        # Make sure the override supplied by the operator using the old policy
        # name is used in favor of the old or new default.
        self.assertFalse(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['fizz']})
        )
        self.assertFalse(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['bang']})
        )
        self.assertTrue(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['bazz']})
        )

    def test_override_deprecated_policy_with_new_name(self):
        # Simulate an operator overriding a policy using the new policy name
        rules = jsonutils.dumps({'foo:create_bar': 'role:bazz'})
        self.create_config_file('policy.json', rules)

        # Deprecate the policy name and check string in favor of something
        # better.
        deprecated_rule = policy.DeprecatedRule(
            name='foo:bar',
            check_str='role:fizz'
        )
        rule_list = [policy.DocumentedRuleDefault(
            name='foo:create_bar',
            check_str='role:bang',
            description='Create a bar.',
            operations=[{'path': '/v1/bars', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason='"role:bang" is a better default',
            deprecated_since='N'
        )]
        self.enforcer.register_defaults(rule_list)

        # Make sure the override supplied by the operator is being used in
        # place of either default value.
        self.assertFalse(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['fizz']})
        )
        self.assertFalse(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['bang']})
        )
        self.assertTrue(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['bazz']})
        )

    def test_override_both_new_and_old_policy(self):
        # Simulate an operator overriding a policy using both the the new and
        # old policy names. The following doesn't make a whole lot of sense
        # because the overrides are conflicting, but we want to make sure that
        # oslo.policy uses foo:create_bar instead of foo:bar.
        rules_dict = {
            'foo:create_bar': 'role:bazz',
            'foo:bar': 'role:wee'
        }
        rules = jsonutils.dumps(rules_dict)
        self.create_config_file('policy.json', rules)

        # Deprecate the policy name and check string in favor of something
        # better.
        deprecated_rule = policy.DeprecatedRule(
            name='foo:bar',
            check_str='role:fizz'
        )
        rule_list = [policy.DocumentedRuleDefault(
            name='foo:create_bar',
            check_str='role:bang',
            description='Create a bar.',
            operations=[{'path': '/v1/bars', 'method': 'POST'}],
            deprecated_rule=deprecated_rule,
            deprecated_reason='"role:bang" is a better default',
            deprecated_since='N'
        )]
        self.enforcer.register_defaults(rule_list)

        # The default check string for the old policy name foo:bar should fail
        self.assertFalse(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['fizz']})
        )

        # The default check string for the new policy name foo:create_bar
        # should fail
        self.assertFalse(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['bang']})
        )

        # The override for the old policy name foo:bar should fail
        self.assertFalse(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['wee']})
        )

        # The override for foo:create_bar should pass
        self.assertTrue(
            self.enforcer.enforce('foo:create_bar', {}, {'roles': ['bazz']})
        )


class DocumentedRuleDefaultTestCase(base.PolicyBaseTestCase):

    def test_contain_operations(self):
        opt = policy.DocumentedRuleDefault(
            name='foo', check_str='rule:foo', description='foo_api',
            operations=[{'path': '/foo/', 'method': 'GET'}])

        self.assertEqual(1, len(opt.operations))

    def test_multiple_operations(self):
        opt = policy.DocumentedRuleDefault(
            name='foo', check_str='rule:foo', description='foo_api',
            operations=[{'path': '/foo/', 'method': 'GET'},
                        {'path': '/foo/', 'method': 'POST'}])

        self.assertEqual(2, len(opt.operations))

    def test_description_not_empty(self):
        invalid_desc = ''
        self.assertRaises(policy.InvalidRuleDefault,
                          policy.DocumentedRuleDefault,
                          name='foo',
                          check_str='rule:foo',
                          description=invalid_desc,
                          operations=[{'path': '/foo/', 'method': 'GET'}])

    def test_operation_not_empty_list(self):
        invalid_op = []
        self.assertRaises(policy.InvalidRuleDefault,
                          policy.DocumentedRuleDefault,
                          name='foo',
                          check_str='rule:foo',
                          description='foo_api',
                          operations=invalid_op)

    def test_operation_must_be_list(self):
        invalid_op = 'invalid_op'
        self.assertRaises(policy.InvalidRuleDefault,
                          policy.DocumentedRuleDefault,
                          name='foo',
                          check_str='rule:foo',
                          description='foo_api',
                          operations=invalid_op)

    def test_operation_must_be_list_of_dicts(self):
        invalid_op = ['invalid_op']
        self.assertRaises(policy.InvalidRuleDefault,
                          policy.DocumentedRuleDefault,
                          name='foo',
                          check_str='rule:foo',
                          description='foo_api',
                          operations=invalid_op)

    def test_operation_must_have_path(self):
        invalid_op = [{'method': 'POST'}]
        self.assertRaises(policy.InvalidRuleDefault,
                          policy.DocumentedRuleDefault,
                          name='foo',
                          check_str='rule:foo',
                          description='foo_api',
                          operations=invalid_op)

    def test_operation_must_have_method(self):
        invalid_op = [{'path': '/foo/path/'}]
        self.assertRaises(policy.InvalidRuleDefault,
                          policy.DocumentedRuleDefault,
                          name='foo',
                          check_str='rule:foo',
                          description='foo_api',
                          operations=invalid_op)

    def test_operation_must_contain_method_and_path_only(self):
        invalid_op = [{'path': '/some/path/',
                       'method': 'GET',
                       'break': 'me'}]
        self.assertRaises(policy.InvalidRuleDefault,
                          policy.DocumentedRuleDefault,
                          name='foo',
                          check_str='rule:foo',
                          description='foo_api',
                          operations=invalid_op)


class EnforcerCheckRulesTest(base.PolicyBaseTestCase):
    def setUp(self):
        super(EnforcerCheckRulesTest, self).setUp()

    def test_no_violations(self):
        self.create_config_file('policy.json', POLICY_JSON_CONTENTS)
        self.enforcer.load_rules(True)
        self.assertTrue(self.enforcer.check_rules(raise_on_violation=True))

    def test_undefined_rule(self):
        rules = jsonutils.dumps({'foo': 'rule:bar'})
        self.create_config_file('policy.json', rules)
        self.enforcer.load_rules(True)

        self.assertFalse(self.enforcer.check_rules())

    def test_undefined_rule_raises(self):
        rules = jsonutils.dumps({'foo': 'rule:bar'})
        self.create_config_file('policy.json', rules)
        self.enforcer.load_rules(True)

        self.assertRaises(policy.InvalidDefinitionError,
                          self.enforcer.check_rules, raise_on_violation=True)

    def test_cyclical_rules(self):
        rules = jsonutils.dumps({'foo': 'rule:bar', 'bar': 'rule:foo'})
        self.create_config_file('policy.json', rules)
        self.enforcer.load_rules(True)

        self.assertFalse(self.enforcer.check_rules())

    def test_cyclical_rules_raises(self):
        rules = jsonutils.dumps({'foo': 'rule:bar', 'bar': 'rule:foo'})
        self.create_config_file('policy.json', rules)
        self.enforcer.load_rules(True)

        self.assertRaises(policy.InvalidDefinitionError,
                          self.enforcer.check_rules, raise_on_violation=True)

    def test_complex_cyclical_rules_false(self):
        rules = jsonutils.dumps({'foo': 'rule:bar',
                                 'bar': 'rule:baz and role:admin',
                                 'baz': 'rule:foo or role:user'})
        self.create_config_file('policy.json', rules)
        self.enforcer.load_rules(True)

        self.assertFalse(self.enforcer.check_rules())

    def test_complex_cyclical_rules_true(self):
        rules = jsonutils.dumps({'foo': 'rule:bar or rule:baz',
                                 'bar': 'role:admin',
                                 'baz': 'rule:bar or role:user'})
        self.create_config_file('policy.json', rules)
        self.enforcer.load_rules(True)

        self.assertTrue(self.enforcer.check_rules())
