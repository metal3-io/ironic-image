# Copyright 2015 Red Hat, Inc.
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

"""Tests for introspection rules plugins."""

from ironicclient import exceptions
import mock

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import node_cache
from ironic_inspector.plugins import rules as rules_plugins
from ironic_inspector.test import base as test_base
from ironic_inspector import utils


TEST_SET = [(42, 42), ('42', 42), ('4.2', 4.2),
            (42, 41), ('42', 41), ('4.2', 4.0),
            (41, 42), ('41', 42), ('4.0', 4.2)]


class TestSimpleConditions(test_base.BaseTest):
    def test_validate(self):
        cond = rules_plugins.SimpleCondition()
        cond.validate({'value': 42})
        self.assertRaises(ValueError, cond.validate, {})

    def _test(self, cond, expected, value, ref):
        self.assertIs(expected, cond.check(None, value, {'value': ref}))

    def test_eq(self):
        cond = rules_plugins.EqCondition()
        for values, expected in zip(TEST_SET, [True] * 3 + [False] * 6):
            self._test(cond, expected, *values)
        self._test(cond, True, 'foo', 'foo')
        self._test(cond, False, 'foo', 'bar')

    def test_ne(self):
        cond = rules_plugins.NeCondition()
        for values, expected in zip(TEST_SET, [False] * 3 + [True] * 6):
            self._test(cond, expected, *values)
        self._test(cond, False, 'foo', 'foo')
        self._test(cond, True, 'foo', 'bar')

    def test_gt(self):
        cond = rules_plugins.GtCondition()
        for values, expected in zip(TEST_SET, [False] * 3 + [True] * 3
                                    + [False] * 3):
            self._test(cond, expected, *values)

    def test_ge(self):
        cond = rules_plugins.GeCondition()
        for values, expected in zip(TEST_SET, [True] * 6 + [False] * 3):
            self._test(cond, expected, *values)

    def test_le(self):
        cond = rules_plugins.LeCondition()
        for values, expected in zip(TEST_SET, [True] * 3 + [False] * 3
                                    + [True] * 3):
            self._test(cond, expected, *values)

    def test_lt(self):
        cond = rules_plugins.LtCondition()
        for values, expected in zip(TEST_SET, [False] * 6 + [True] * 3):
            self._test(cond, expected, *values)


class TestReConditions(test_base.BaseTest):
    def test_validate(self):
        for cond in (rules_plugins.MatchesCondition(),
                     rules_plugins.ContainsCondition()):
            cond.validate({'value': r'[a-z]?(foo|b.r).+'})
            self.assertRaises(ValueError, cond.validate,
                              {'value': '**'})

    def test_matches(self):
        cond = rules_plugins.MatchesCondition()
        for reg, field, res in [(r'.*', 'foo', True),
                                (r'fo{1,2}', 'foo', True),
                                (r'o{1,2}', 'foo', False),
                                (r'[1-9]*', 42, True),
                                (r'^(foo|bar)$', 'foo', True),
                                (r'fo', 'foo', False)]:
            self.assertEqual(res, cond.check(None, field, {'value': reg}))

    def test_contains(self):
        cond = rules_plugins.ContainsCondition()
        for reg, field, res in [(r'.*', 'foo', True),
                                (r'fo{1,2}', 'foo', True),
                                (r'o{1,2}', 'foo', True),
                                (r'[1-9]*', 42, True),
                                (r'bar', 'foo', False)]:
            self.assertEqual(res, cond.check(None, field, {'value': reg}))


class TestNetCondition(test_base.BaseTest):
    cond = rules_plugins.NetCondition()

    def test_validate(self):
        self.cond.validate({'value': '192.0.2.1/24'})
        self.assertRaises(ValueError, self.cond.validate, {'value': 'foo'})

    def test_check(self):
        self.assertTrue(self.cond.check(None, '192.0.2.4',
                                        {'value': '192.0.2.1/24'}))
        self.assertFalse(self.cond.check(None, '192.1.2.4',
                                         {'value': '192.0.2.1/24'}))


class TestEmptyCondition(test_base.BaseTest):
    cond = rules_plugins.EmptyCondition()

    def test_check_none(self):
        self.assertTrue(self.cond.check(None, None, {}))
        self.assertFalse(self.cond.check(None, 0, {}))

    def test_check_empty_string(self):
        self.assertTrue(self.cond.check(None, '', {}))
        self.assertFalse(self.cond.check(None, '16', {}))

    def test_check_empty_list(self):
        self.assertTrue(self.cond.check(None, [], {}))
        self.assertFalse(self.cond.check(None, ['16'], {}))

    def test_check_empty_dict(self):
        self.assertTrue(self.cond.check(None, {}, {}))
        self.assertFalse(self.cond.check(None, {'test': '16'}, {}))


class TestFailAction(test_base.BaseTest):
    act = rules_plugins.FailAction()

    def test_validate(self):
        self.act.validate({'message': 'boom'})
        self.assertRaises(ValueError, self.act.validate, {})

    def test_apply(self):
        self.assertRaisesRegex(utils.Error, 'boom',
                               self.act.apply, None, {'message': 'boom'})


class TestSetAttributeAction(test_base.NodeTest):
    act = rules_plugins.SetAttributeAction()
    params = {'path': '/extra/value', 'value': 42}

    def test_validate(self):
        self.act.validate(self.params)
        self.assertRaises(ValueError, self.act.validate, {'value': 42})
        self.assertRaises(ValueError, self.act.validate,
                          {'path': '/extra/value'})
        self.params['value'] = None
        self.act.validate(self.params)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply(self, mock_patch):
        self.act.apply(self.node_info, self.params)
        mock_patch.assert_called_once_with([{'op': 'add',
                                             'path': '/extra/value',
                                             'value': 42}])

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply_driver(self, mock_patch):
        params = {'path': '/driver', 'value': 'ipmi'}
        self.act.apply(self.node_info, params)
        mock_patch.assert_called_once_with([{'op': 'add',
                                             'path': '/driver',
                                             'value': 'ipmi'}],
                                           reset_interfaces=True)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply_driver_no_reset_interfaces(self, mock_patch):
        params = {'path': '/driver', 'value': 'ipmi',
                  'reset_interfaces': False}
        self.act.apply(self.node_info, params)
        mock_patch.assert_called_once_with([{'op': 'add',
                                             'path': '/driver',
                                             'value': 'ipmi'}])

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply_driver_not_supported(self, mock_patch):
        for exc in (TypeError, exceptions.NotAcceptable):
            mock_patch.reset_mock()
            mock_patch.side_effect = [exc, None]
            params = {'path': '/driver', 'value': 'ipmi'}
            self.act.apply(self.node_info, params)
            mock_patch.assert_has_calls([
                mock.call([{'op': 'add', 'path': '/driver', 'value': 'ipmi'}],
                          reset_interfaces=True),
                mock.call([{'op': 'add', 'path': '/driver', 'value': 'ipmi'}])
            ])


@mock.patch('ironic_inspector.common.ironic.get_client', new=mock.Mock())
class TestSetCapabilityAction(test_base.NodeTest):
    act = rules_plugins.SetCapabilityAction()
    params = {'name': 'cap1', 'value': 'val'}

    def test_validate(self):
        self.act.validate(self.params)
        self.assertRaises(ValueError, self.act.validate, {'value': 42})

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply(self, mock_patch):
        self.act.apply(self.node_info, self.params)
        mock_patch.assert_called_once_with(
            [{'op': 'add', 'path': '/properties/capabilities',
              'value': 'cap1:val'}], mock.ANY)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply_with_existing(self, mock_patch):
        self.node.properties['capabilities'] = 'x:y,cap1:old_val,answer:42'
        self.act.apply(self.node_info, self.params)

        patch = mock_patch.call_args[0][0]
        new_caps = ir_utils.capabilities_to_dict(patch[0]['value'])
        self.assertEqual({'cap1': 'val', 'x': 'y', 'answer': '42'}, new_caps)


@mock.patch('ironic_inspector.common.ironic.get_client', new=mock.Mock())
class TestExtendAttributeAction(test_base.NodeTest):
    act = rules_plugins.ExtendAttributeAction()
    params = {'path': '/extra/value', 'value': 42}

    def test_validate(self):
        self.act.validate(self.params)
        self.assertRaises(ValueError, self.act.validate, {'value': 42})

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply(self, mock_patch):
        self.act.apply(self.node_info, self.params)
        mock_patch.assert_called_once_with(
            [{'op': 'add', 'path': '/extra/value', 'value': [42]}], mock.ANY)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply_non_empty(self, mock_patch):
        self.node.extra['value'] = [0]
        self.act.apply(self.node_info, self.params)

        mock_patch.assert_called_once_with(
            [{'op': 'replace', 'path': '/extra/value', 'value': [0, 42]}],
            mock.ANY)

    @mock.patch.object(node_cache.NodeInfo, 'patch')
    def test_apply_unique_with_existing(self, mock_patch):
        params = dict(unique=True, **self.params)
        self.node.extra['value'] = [42]
        self.act.apply(self.node_info, params)
        self.assertFalse(mock_patch.called)


@mock.patch('ironic_inspector.common.ironic.get_client', autospec=True)
class TestAddTraitAction(test_base.NodeTest):
    act = rules_plugins.AddTraitAction()
    params = {'name': 'CUSTOM_FOO'}

    def test_validate(self, mock_cli):
        self.act.validate(self.params)
        self.assertRaises(ValueError, self.act.validate, {'value': 42})

    def test_add(self, mock_cli):
        self.act.apply(self.node_info, self.params)
        mock_cli.return_value.node.add_trait.assert_called_once_with(
            self.uuid, 'CUSTOM_FOO')


@mock.patch('ironic_inspector.common.ironic.get_client', autospec=True)
class TestRemoveTraitAction(test_base.NodeTest):
    act = rules_plugins.RemoveTraitAction()
    params = {'name': 'CUSTOM_FOO'}

    def test_validate(self, mock_cli):
        self.act.validate(self.params)
        self.assertRaises(ValueError, self.act.validate, {'value': 42})

    def test_remove(self, mock_cli):
        self.act.apply(self.node_info, self.params)
        mock_cli.return_value.node.remove_trait.assert_called_once_with(
            self.uuid, 'CUSTOM_FOO')

    def test_remove_not_found(self, mock_cli):
        mock_cli.return_value.node.remove_trait.side_effect = (
            exceptions.NotFound('trait not found'))
        self.act.apply(self.node_info, self.params)
        mock_cli.return_value.node.remove_trait.assert_called_once_with(
            self.uuid, 'CUSTOM_FOO')
