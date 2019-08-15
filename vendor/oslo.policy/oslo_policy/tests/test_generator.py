#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
# #    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import operator
import warnings

import mock
from oslo_config import cfg
import stevedore
import testtools
import yaml

from oslo_policy import generator
from oslo_policy import policy
from oslo_policy.tests import base
from oslo_serialization import jsonutils


OPTS = {'base_rules': [policy.RuleDefault('admin', 'is_admin:True',
                                          description='Basic admin check'),
                       policy.DocumentedRuleDefault('owner',
                                                    ('project_id:%'
                                                     '(project_id)s'),
                                                    'This is a long '
                                                    'description to check '
                                                    'that line wrapping '
                                                    'functions properly',
                                                    [{'path': '/foo/',
                                                      'method': 'GET'},
                                                     {'path': '/test/',
                                                      'method': 'POST'}])],
        'custom_field': [policy.RuleDefault('shared',
                                            'field:networks:shared=True')],
        'rules': [policy.RuleDefault('admin_or_owner',
                                     'rule:admin or rule:owner')],
        }


class GenerateSampleYAMLTestCase(base.PolicyBaseTestCase):
    def setUp(self):
        super(GenerateSampleYAMLTestCase, self).setUp()
        self.enforcer = policy.Enforcer(self.conf, policy_file='policy.yaml')

    def test_generate_loadable_yaml(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        output_file = self.get_config_file_fullname('policy.yaml')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            # generate sample-policy file with only rules
            generator._generate_sample(['base_rules', 'rules'], output_file,
                                       include_help=False)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['base_rules', 'rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        self.enforcer.load_rules()

        self.assertIn('owner', self.enforcer.rules)
        self.assertIn('admin', self.enforcer.rules)
        self.assertIn('admin_or_owner', self.enforcer.rules)
        self.assertEqual('project_id:%(project_id)s',
                         str(self.enforcer.rules['owner']))
        self.assertEqual('is_admin:True', str(self.enforcer.rules['admin']))
        self.assertEqual('(rule:admin or rule:owner)',
                         str(self.enforcer.rules['admin_or_owner']))

    def test_expected_content(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        expected = '''# Basic admin check
#"admin": "is_admin:True"

# This is a long description to check that line wrapping functions
# properly
# GET  /foo/
# POST  /test/
#"owner": "project_id:%(project_id)s"

#
#"shared": "field:networks:shared=True"

#
#"admin_or_owner": "rule:admin or rule:owner"

'''
        output_file = self.get_config_file_fullname('policy.yaml')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_sample(['base_rules', 'rules'], output_file)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['base_rules', 'rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        with open(output_file, 'r') as written_file:
            written_policy = written_file.read()

        self.assertEqual(expected, written_policy)

    def test_expected_content_stdout(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        expected = '''# Basic admin check
#"admin": "is_admin:True"

# This is a long description to check that line wrapping functions
# properly
# GET  /foo/
# POST  /test/
#"owner": "project_id:%(project_id)s"

#
#"shared": "field:networks:shared=True"

#
#"admin_or_owner": "rule:admin or rule:owner"

'''
        stdout = self._capture_stdout()
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_sample(['base_rules', 'rules'],
                                       output_file=None)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['base_rules', 'rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        self.assertEqual(expected, stdout.getvalue())

    def test_policies_deprecated_for_removal(self):
        rule = policy.RuleDefault(
            name='foo:post_bar',
            check_str='role:fizz',
            description='Create a bar.',
            deprecated_for_removal=True,
            deprecated_reason='This policy is not used anymore',
            deprecated_since='N'
        )
        opts = {'rules': [rule]}

        extensions = []
        for name, opts, in opts.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)

        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['rules']
        )

        expected = '''# DEPRECATED
# "foo:post_bar" has been deprecated since N.
# This policy is not used anymore
# Create a bar.
#"foo:post_bar": "role:fizz"

'''
        stdout = self._capture_stdout()
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_sample(['rules'], output_file=None)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True
            )
        self.assertEqual(expected, stdout.getvalue())

    def test_deprecated_policies_are_aliased_to_new_names(self):
        deprecated_rule = policy.DeprecatedRule(
            name='foo:post_bar',
            check_str='role:fizz'
        )
        new_rule = policy.RuleDefault(
            name='foo:create_bar',
            check_str='role:fizz',
            description='Create a bar.',
            deprecated_rule=deprecated_rule,
            deprecated_reason=(
                'foo:post_bar is being removed in favor of foo:create_bar'
            ),
            deprecated_since='N'
        )
        opts = {'rules': [new_rule]}

        extensions = []
        for name, opts in opts.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['rules'])

        expected = '''# Create a bar.
#"foo:create_bar": "role:fizz"

# DEPRECATED "foo:post_bar":"role:fizz" has been deprecated since N in
# favor of "foo:create_bar":"role:fizz". foo:post_bar is being removed
# in favor of foo:create_bar
"foo:post_bar": "rule:foo:create_bar"
'''
        stdout = self._capture_stdout()
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_sample(['rules'], output_file=None)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True
            )
        self.assertEqual(expected, stdout.getvalue())

    def _test_formatting(self, description, expected):
        rule = [policy.RuleDefault('admin', 'is_admin:True',
                                   description=description)]
        ext = stevedore.extension.Extension(name='check_rule',
                                            entry_point=None,
                                            plugin=None, obj=rule)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=[ext], namespace=['check_rule'])

        output_file = self.get_config_file_fullname('policy.yaml')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_sample(['check_rule'], output_file)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['check_rule'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        with open(output_file, 'r') as written_file:
            written_policy = written_file.read()

        self.assertEqual(expected, written_policy)

    def test_empty_line_formatting(self):
        description = ('Check Summary \n'
                       '\n'
                       'This is a description to '
                       'check that empty line has '
                       'no white spaces.')
        expected = """# Check Summary
#
# This is a description to check that empty line has no white spaces.
#"admin": "is_admin:True"

"""

        self._test_formatting(description, expected)

    def test_paragraph_formatting(self):
        description = """
Here's a neat description with a paragraph. We want to make sure that it wraps
properly.
"""
        expected = """# Here's a neat description with a paragraph. We want \
to make sure
# that it wraps properly.
#"admin": "is_admin:True"

"""

        self._test_formatting(description, expected)

    def test_literal_block_formatting(self):
        description = """Here's another description.

    This one has a literal block.
    These lines should be kept apart.
    They should not be wrapped, even though they may be longer than 70 chars
"""
        expected = """# Here's another description.
#
#     This one has a literal block.
#     These lines should be kept apart.
#     They should not be wrapped, even though they may be longer than 70 chars
#"admin": "is_admin:True"

"""

        self._test_formatting(description, expected)

    def test_invalid_formatting(self):
        description = """Here's a broken description.

We have some text...
    Followed by a literal block without any spaces.
    We don't support definition lists, so this is just wrong!
"""
        expected = """# Here's a broken description.
#
# We have some text...
#
#     Followed by a literal block without any spaces.
#     We don't support definition lists, so this is just wrong!
#"admin": "is_admin:True"

"""

        with warnings.catch_warnings(record=True) as warns:
            self._test_formatting(description, expected)
            self.assertEqual(1, len(warns))
            self.assertTrue(issubclass(warns[-1].category, FutureWarning))
            self.assertIn('Invalid policy description', str(warns[-1].message))


class GenerateSampleJSONTestCase(base.PolicyBaseTestCase):
    def setUp(self):
        super(GenerateSampleJSONTestCase, self).setUp()
        self.enforcer = policy.Enforcer(self.conf, policy_file='policy.json')

    def test_generate_loadable_json(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        output_file = self.get_config_file_fullname('policy.json')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            # generate sample-policy file with only rules
            generator._generate_sample(['base_rules', 'rules'], output_file,
                                       output_format='json',
                                       include_help=False)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['base_rules', 'rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        self.enforcer.load_rules()

        self.assertIn('owner', self.enforcer.rules)
        self.assertIn('admin', self.enforcer.rules)
        self.assertIn('admin_or_owner', self.enforcer.rules)
        self.assertEqual('project_id:%(project_id)s',
                         str(self.enforcer.rules['owner']))
        self.assertEqual('is_admin:True', str(self.enforcer.rules['admin']))
        self.assertEqual('(rule:admin or rule:owner)',
                         str(self.enforcer.rules['admin_or_owner']))

    def test_expected_content(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        expected = '''{
    "admin": "is_admin:True",
    "owner": "project_id:%(project_id)s",
    "shared": "field:networks:shared=True",
    "admin_or_owner": "rule:admin or rule:owner"
}
'''
        output_file = self.get_config_file_fullname('policy.json')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_sample(['base_rules', 'rules'],
                                       output_file=output_file,
                                       output_format='json')
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['base_rules', 'rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        with open(output_file, 'r') as written_file:
            written_policy = written_file.read()

        self.assertEqual(expected, written_policy)

    def test_expected_content_stdout(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        expected = '''{
    "admin": "is_admin:True",
    "owner": "project_id:%(project_id)s",
    "shared": "field:networks:shared=True",
    "admin_or_owner": "rule:admin or rule:owner"
}
'''
        stdout = self._capture_stdout()
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_sample(['base_rules', 'rules'],
                                       output_file=None,
                                       output_format='json')
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.policies', names=['base_rules', 'rules'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        self.assertEqual(expected, stdout.getvalue())


class GeneratorRaiseErrorTestCase(testtools.TestCase):
    def test_generator_raises_error(self):
        """Verifies that errors from extension manager are not suppressed."""
        class FakeException(Exception):
            pass

        class FakeEP(object):

            def __init__(self):
                self.name = 'callback_is_expected'
                self.require = self.resolve
                self.load = self.resolve

            def resolve(self, *args, **kwargs):
                raise FakeException()

        fake_ep = FakeEP()
        fake_eps = mock.Mock(return_value=[fake_ep])
        with mock.patch('pkg_resources.iter_entry_points', fake_eps):
            self.assertRaises(FakeException, generator._generate_sample,
                              fake_ep.name)

    def test_generator_call_with_no_arguments_raises_error(self):
        testargs = ['oslopolicy-sample-generator']
        with mock.patch('sys.argv', testargs):
            self.assertRaises(cfg.RequiredOptError, generator.generate_sample,
                              [])


class GeneratePolicyTestCase(base.PolicyBaseTestCase):
    def setUp(self):
        super(GeneratePolicyTestCase, self).setUp()

    def test_merged_rules(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        # Write the policy file for an enforcer to load
        sample_file = self.get_config_file_fullname('policy-sample.yaml')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr):
            # generate sample-policy file with only rules
            generator._generate_sample(['base_rules', 'rules'], sample_file,
                                       include_help=False)

        enforcer = policy.Enforcer(self.conf, policy_file='policy-sample.yaml')
        # register an opt defined in the file
        enforcer.register_default(policy.RuleDefault('admin',
                                                     'is_admin:False'))
        # register a new opt
        enforcer.register_default(policy.RuleDefault('foo', 'role:foo'))

        # Mock out stevedore to return the configured enforcer
        ext = stevedore.extension.Extension(name='testing', entry_point=None,
                                            plugin=None, obj=enforcer)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=[ext], namespace='testing')

        # Generate a merged file
        merged_file = self.get_config_file_fullname('policy-merged.yaml')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._generate_policy(namespace='testing',
                                       output_file=merged_file)
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.enforcer', names=['testing'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        # load the merged file with a new enforcer
        merged_enforcer = policy.Enforcer(self.conf,
                                          policy_file='policy-merged.yaml')
        merged_enforcer.load_rules()
        for rule in ['admin', 'owner', 'admin_or_owner', 'foo']:
            self.assertIn(rule, merged_enforcer.rules)

        self.assertEqual('is_admin:True', str(merged_enforcer.rules['admin']))
        self.assertEqual('role:foo', str(merged_enforcer.rules['foo']))


class ListRedundantTestCase(base.PolicyBaseTestCase):
    def setUp(self):
        super(ListRedundantTestCase, self).setUp()

    def test_matched_rules(self):
        extensions = []
        for name, opts in OPTS.items():
            ext = stevedore.extension.Extension(name=name, entry_point=None,
                                                plugin=None, obj=opts)
            extensions.append(ext)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=extensions, namespace=['base_rules', 'rules'])

        # Write the policy file for an enforcer to load
        sample_file = self.get_config_file_fullname('policy-sample.yaml')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr):
            # generate sample-policy file with only rules
            generator._generate_sample(['base_rules', 'rules'], sample_file,
                                       include_help=False)

        enforcer = policy.Enforcer(self.conf, policy_file='policy-sample.yaml')
        # register opts that match those defined in policy-sample.yaml
        enforcer.register_default(policy.RuleDefault('admin', 'is_admin:True'))
        enforcer.register_default(
            policy.RuleDefault('owner', 'project_id:%(project_id)s'))
        # register a new opt
        enforcer.register_default(policy.RuleDefault('foo', 'role:foo'))

        # Mock out stevedore to return the configured enforcer
        ext = stevedore.extension.Extension(name='testing', entry_point=None,
                                            plugin=None, obj=enforcer)
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=[ext], namespace='testing')

        stdout = self._capture_stdout()
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr) as mock_ext_mgr:
            generator._list_redundant(namespace='testing')
            mock_ext_mgr.assert_called_once_with(
                'oslo.policy.enforcer', names=['testing'],
                on_load_failure_callback=generator.on_load_failure_callback,
                invoke_on_load=True)

        matches = [line.split(': ', 1) for
                   line in stdout.getvalue().splitlines()]
        matches.sort(key=operator.itemgetter(0))

        # Should be 'admin'
        opt0 = matches[0]
        self.assertEqual('"admin"', opt0[0])
        self.assertEqual('"is_admin:True"', opt0[1])

        # Should be 'owner'
        opt1 = matches[1]
        self.assertEqual('"owner"', opt1[0])
        self.assertEqual('"project_id:%(project_id)s"', opt1[1])


class UpgradePolicyTestCase(base.PolicyBaseTestCase):
    def setUp(self):
        super(UpgradePolicyTestCase, self).setUp()
        policy_json_contents = jsonutils.dumps({
            "deprecated_name": "rule:admin"
        })
        self.create_config_file('policy.json', policy_json_contents)
        deprecated_policy = policy.DeprecatedRule(
            name='deprecated_name',
            check_str='rule:admin'
        )
        self.new_policy = policy.DocumentedRuleDefault(
            name='new_policy_name',
            check_str='rule:admin',
            description='test_policy',
            operations=[{'path': '/test', 'method': 'GET'}],
            deprecated_rule=deprecated_policy,
            deprecated_reason='test',
            deprecated_since='Stein'
        )
        self.extensions = []
        ext = stevedore.extension.Extension(name='test_upgrade',
                                            entry_point=None,
                                            plugin=None,
                                            obj=[self.new_policy])
        self.extensions.append(ext)

    def test_upgrade_policy_json_file(self):
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=self.extensions, namespace='test_upgrade')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr):
            testargs = ['olsopolicy-policy-upgrade',
                        '--policy',
                        self.get_config_file_fullname('policy.json'),
                        '--namespace', 'test_upgrade',
                        '--output-file',
                        self.get_config_file_fullname('new_policy.json'),
                        '--format', 'json']
            with mock.patch('sys.argv', testargs):
                generator.upgrade_policy()
                new_file = self.get_config_file_fullname('new_policy.json')
                new_policy = jsonutils.loads(open(new_file, 'r').read())
                self.assertIsNotNone(new_policy.get('new_policy_name'))
                self.assertIsNone(new_policy.get('deprecated_name'))

    def test_upgrade_policy_yaml_file(self):
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=self.extensions, namespace='test_upgrade')
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr):
            testargs = ['olsopolicy-policy-upgrade',
                        '--policy',
                        self.get_config_file_fullname('policy.json'),
                        '--namespace', 'test_upgrade',
                        '--output-file',
                        self.get_config_file_fullname('new_policy.yaml'),
                        '--format', 'yaml']
            with mock.patch('sys.argv', testargs):
                generator.upgrade_policy()
                new_file = self.get_config_file_fullname('new_policy.yaml')
                new_policy = yaml.safe_load(open(new_file, 'r'))
                self.assertIsNotNone(new_policy.get('new_policy_name'))
                self.assertIsNone(new_policy.get('deprecated_name'))

    def test_upgrade_policy_json_stdout(self):
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=self.extensions, namespace='test_upgrade')
        stdout = self._capture_stdout()
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr):
            testargs = ['olsopolicy-policy-upgrade',
                        '--policy',
                        self.get_config_file_fullname('policy.json'),
                        '--namespace', 'test_upgrade',
                        '--format', 'json']
            with mock.patch('sys.argv', testargs):
                generator.upgrade_policy()
                expected = '''{
    "new_policy_name": "rule:admin"
}'''
                self.assertEqual(expected, stdout.getvalue())

    def test_upgrade_policy_yaml_stdout(self):
        test_mgr = stevedore.named.NamedExtensionManager.make_test_instance(
            extensions=self.extensions, namespace='test_upgrade')
        stdout = self._capture_stdout()
        with mock.patch('stevedore.named.NamedExtensionManager',
                        return_value=test_mgr):
            testargs = ['olsopolicy-policy-upgrade',
                        '--policy',
                        self.get_config_file_fullname('policy.json'),
                        '--namespace', 'test_upgrade',
                        '--format', 'yaml']
            with mock.patch('sys.argv', testargs):
                generator.upgrade_policy()
                expected = '''new_policy_name: rule:admin
'''
                self.assertEqual(expected, stdout.getvalue())


@mock.patch('stevedore.named.NamedExtensionManager')
class GetEnforcerTestCase(base.PolicyBaseTestCase):
    def test_get_enforcer(self, mock_manager):
        mock_instance = mock.MagicMock()
        mock_instance.__contains__.return_value = True
        mock_manager.return_value = mock_instance
        mock_item = mock.Mock()
        mock_item.obj = 'test'
        mock_instance.__getitem__.return_value = mock_item
        self.assertEqual('test', generator._get_enforcer('foo'))

    def test_get_enforcer_missing(self, mock_manager):
        mock_instance = mock.MagicMock()
        mock_instance.__contains__.return_value = False
        mock_manager.return_value = mock_instance
        self.assertRaises(KeyError, generator._get_enforcer, 'nonexistent')
