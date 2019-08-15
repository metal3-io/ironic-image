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

"""Tests for introspection rules."""
import mock
from oslo_utils import uuidutils

from ironic_inspector import db
from ironic_inspector.plugins import base as plugins_base
from ironic_inspector import rules
from ironic_inspector.test import base as test_base
from ironic_inspector import utils


class BaseTest(test_base.NodeTest):
    def setUp(self):
        super(BaseTest, self).setUp()
        self.uuid = uuidutils.generate_uuid()
        self.conditions_json = [
            {'op': 'eq', 'field': 'memory_mb', 'value': 1024},
            {'op': 'eq', 'field': 'local_gb', 'value': 60},
        ]
        self.actions_json = [
            {'action': 'fail', 'message': 'boom!'}
        ]

        self.data = {
            'memory_mb': 1024,
            'local_gb': 42,
        }

    @staticmethod
    def condition_defaults(condition):
        condition = condition.copy()
        condition.setdefault('multiple', 'any')
        condition.setdefault('invert', False)
        return condition


class TestCreateRule(BaseTest):
    def test_only_actions(self):
        rule = rules.create([], self.actions_json)
        rule_json = rule.as_dict()

        self.assertTrue(rule_json.pop('uuid'))
        self.assertEqual({'description': None,
                          'conditions': [],
                          'actions': self.actions_json},
                         rule_json)

    def test_create_action_none_value(self):
        self.actions_json = [{'action': 'set-attribute',
                              'path': '/properties/cpus', 'value': None}]
        rule = rules.create([], self.actions_json)
        rule_json = rule.as_dict()

        self.assertTrue(rule_json.pop('uuid'))
        self.assertEqual({'description': None,
                          'conditions': [],
                          'actions': self.actions_json},
                         rule_json)

    def test_duplicate_uuid(self):
        rules.create([], self.actions_json, uuid=self.uuid)
        self.assertRaisesRegex(utils.Error, 'already exists',
                               rules.create, [], self.actions_json,
                               uuid=self.uuid)

    def test_with_conditions(self):
        self.conditions_json.extend([
            # multiple present&default, invert absent
            {'op': 'eq', 'field': 'local_gb', 'value': 60, 'multiple': 'any'},
            # multiple absent, invert present&default
            {'op': 'eq', 'field': 'local_gb', 'value': 60, 'invert': False},
            # multiple&invert present&non-default
            {'op': 'eq', 'field': 'memory_mb', 'value': 1024,
             'multiple': 'all', 'invert': True},
        ])
        rule = rules.create(self.conditions_json, self.actions_json)
        rule_json = rule.as_dict()

        self.assertTrue(rule_json.pop('uuid'))
        self.assertEqual({'description': None,
                          'conditions': [BaseTest.condition_defaults(cond)
                                         for cond in self.conditions_json],
                          'actions': self.actions_json},
                         rule_json)

    def test_invalid_condition(self):
        del self.conditions_json[0]['op']

        self.assertRaisesRegex(utils.Error,
                               'Validation failed for conditions',
                               rules.create,
                               self.conditions_json, self.actions_json)

        self.conditions_json[0]['op'] = 'foobar'

        self.assertRaisesRegex(utils.Error,
                               'Validation failed for conditions',
                               rules.create,
                               self.conditions_json, self.actions_json)

    def test_invalid_condition_field(self):
        self.conditions_json[0]['field'] = '!*!'

        self.assertRaisesRegex(utils.Error,
                               'Unable to parse field JSON path',
                               rules.create,
                               self.conditions_json, self.actions_json)

    def test_invalid_condition_parameters(self):
        self.conditions_json[0]['foo'] = 'bar'

        self.assertRaisesRegex(utils.Error,
                               'Invalid parameters for operator',
                               rules.create,
                               self.conditions_json, self.actions_json)

    def test_no_actions(self):
        self.assertRaisesRegex(utils.Error,
                               'Validation failed for actions',
                               rules.create,
                               self.conditions_json, [])

    def test_invalid_action(self):
        del self.actions_json[0]['action']

        self.assertRaisesRegex(utils.Error,
                               'Validation failed for actions',
                               rules.create,
                               self.conditions_json, self.actions_json)

        self.actions_json[0]['action'] = 'foobar'

        self.assertRaisesRegex(utils.Error,
                               'Validation failed for actions',
                               rules.create,
                               self.conditions_json, self.actions_json)

    def test_invalid_action_parameters(self):
        self.actions_json[0]['foo'] = 'bar'

        self.assertRaisesRegex(utils.Error,
                               'Invalid parameters for action',
                               rules.create,
                               self.conditions_json, self.actions_json)


class TestGetRule(BaseTest):
    def setUp(self):
        super(TestGetRule, self).setUp()
        rules.create(self.conditions_json, self.actions_json, uuid=self.uuid)

    def test_get(self):
        rule_json = rules.get(self.uuid).as_dict()

        self.assertTrue(rule_json.pop('uuid'))
        self.assertEqual({'description': None,
                          'conditions': [BaseTest.condition_defaults(cond)
                                         for cond in self.conditions_json],
                          'actions': self.actions_json},
                         rule_json)

    def test_not_found(self):
        self.assertRaises(utils.Error, rules.get, 'foobar')

    def test_get_all(self):
        uuid2 = uuidutils.generate_uuid()
        rules.create(self.conditions_json, self.actions_json, uuid=uuid2)
        self.assertEqual({self.uuid, uuid2},
                         {r.as_dict()['uuid'] for r in rules.get_all()})


class TestDeleteRule(BaseTest):
    def setUp(self):
        super(TestDeleteRule, self).setUp()
        self.uuid2 = uuidutils.generate_uuid()
        rules.create(self.conditions_json, self.actions_json, uuid=self.uuid)
        rules.create(self.conditions_json, self.actions_json, uuid=self.uuid2)

    def test_delete(self):
        rules.delete(self.uuid)

        self.assertEqual([(self.uuid2,)], db.model_query(db.Rule.uuid).all())
        self.assertFalse(db.model_query(db.RuleCondition)
                         .filter_by(rule=self.uuid).all())
        self.assertFalse(db.model_query(db.RuleAction)
                         .filter_by(rule=self.uuid).all())

    def test_delete_non_existing(self):
        self.assertRaises(utils.Error, rules.delete, 'foo')

    def test_delete_all(self):
        rules.delete_all()

        self.assertFalse(db.model_query(db.Rule).all())
        self.assertFalse(db.model_query(db.RuleCondition).all())
        self.assertFalse(db.model_query(db.RuleAction).all())


@mock.patch.object(plugins_base, 'rule_conditions_manager', autospec=True)
class TestCheckConditions(BaseTest):
    def setUp(self):
        super(TestCheckConditions, self).setUp()

        self.rule = rules.create(conditions_json=self.conditions_json,
                                 actions_json=self.actions_json)
        self.cond_mock = mock.Mock(spec=plugins_base.RuleConditionPlugin)
        self.cond_mock.ALLOW_NONE = False
        self.ext_mock = mock.Mock(spec=['obj'], obj=self.cond_mock)

    def test_ok(self, mock_ext_mgr):
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock
        self.cond_mock.check.return_value = True

        res = self.rule.check_conditions(self.node_info, self.data)

        self.cond_mock.check.assert_any_call(self.node_info, 1024,
                                             {'value': 1024})
        self.cond_mock.check.assert_any_call(self.node_info, 42,
                                             {'value': 60})
        self.assertEqual(len(self.conditions_json),
                         self.cond_mock.check.call_count)
        self.assertTrue(res)

    def test_invert(self, mock_ext_mgr):
        self.conditions_json = [
            {'op': 'eq', 'field': 'memory_mb', 'value': 42,
             'invert': True},
        ]
        self.rule = rules.create(conditions_json=self.conditions_json,
                                 actions_json=self.actions_json)

        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock
        self.cond_mock.check.return_value = False

        res = self.rule.check_conditions(self.node_info, self.data)

        self.cond_mock.check.assert_called_once_with(self.node_info, 1024,
                                                     {'value': 42})
        self.assertTrue(res)

    def test_no_field(self, mock_ext_mgr):
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock
        self.cond_mock.check.return_value = True
        del self.data['local_gb']

        res = self.rule.check_conditions(self.node_info, self.data)

        self.cond_mock.check.assert_called_once_with(self.node_info, 1024,
                                                     {'value': 1024})
        self.assertFalse(res)

    def test_no_field_none_allowed(self, mock_ext_mgr):
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock
        self.cond_mock.ALLOW_NONE = True
        self.cond_mock.check.return_value = True
        del self.data['local_gb']

        res = self.rule.check_conditions(self.node_info, self.data)

        self.cond_mock.check.assert_any_call(self.node_info, 1024,
                                             {'value': 1024})
        self.cond_mock.check.assert_any_call(self.node_info, None,
                                             {'value': 60})
        self.assertEqual(len(self.conditions_json),
                         self.cond_mock.check.call_count)
        self.assertTrue(res)

    def test_fail(self, mock_ext_mgr):
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock
        self.cond_mock.check.return_value = False

        res = self.rule.check_conditions(self.node_info, self.data)

        self.cond_mock.check.assert_called_once_with(self.node_info, 1024,
                                                     {'value': 1024})
        self.assertFalse(res)


class TestCheckConditionsMultiple(BaseTest):
    def setUp(self):
        super(TestCheckConditionsMultiple, self).setUp()

        self.conditions_json = [
            {'op': 'eq', 'field': 'interfaces[*].ip', 'value': '1.2.3.4'}
        ]

    def _build_data(self, ips):
        return {
            'interfaces': [
                {'ip': ip} for ip in ips
            ]
        }

    def test_default(self):
        rule = rules.create(conditions_json=self.conditions_json,
                            actions_json=self.actions_json)
        data_set = [
            (['1.1.1.1', '1.2.3.4', '1.3.2.2'], True),
            (['1.2.3.4'], True),
            (['1.1.1.1', '1.3.2.2'], False),
            (['1.2.3.4', '1.3.2.2'], True),
        ]
        for ips, result in data_set:
            data = self._build_data(ips)
            self.assertIs(result, rule.check_conditions(self.node_info, data),
                          data)

    def test_any(self):
        self.conditions_json[0]['multiple'] = 'any'
        rule = rules.create(conditions_json=self.conditions_json,
                            actions_json=self.actions_json)
        data_set = [
            (['1.1.1.1', '1.2.3.4', '1.3.2.2'], True),
            (['1.2.3.4'], True),
            (['1.1.1.1', '1.3.2.2'], False),
            (['1.2.3.4', '1.3.2.2'], True),
        ]
        for ips, result in data_set:
            data = self._build_data(ips)
            self.assertIs(result, rule.check_conditions(self.node_info, data),
                          data)

    def test_all(self):
        self.conditions_json[0]['multiple'] = 'all'
        rule = rules.create(conditions_json=self.conditions_json,
                            actions_json=self.actions_json)
        data_set = [
            (['1.1.1.1', '1.2.3.4', '1.3.2.2'], False),
            (['1.2.3.4'], True),
            (['1.1.1.1', '1.3.2.2'], False),
            (['1.2.3.4', '1.3.2.2'], False),
        ]
        for ips, result in data_set:
            data = self._build_data(ips)
            self.assertIs(result, rule.check_conditions(self.node_info, data),
                          data)

    def test_first(self):
        self.conditions_json[0]['multiple'] = 'first'
        rule = rules.create(conditions_json=self.conditions_json,
                            actions_json=self.actions_json)
        data_set = [
            (['1.1.1.1', '1.2.3.4', '1.3.2.2'], False),
            (['1.2.3.4'], True),
            (['1.1.1.1', '1.3.2.2'], False),
            (['1.2.3.4', '1.3.2.2'], True),
        ]
        for ips, result in data_set:
            data = self._build_data(ips)
            self.assertIs(result, rule.check_conditions(self.node_info, data),
                          data)


class TestCheckConditionsSchemePath(BaseTest):
    def test_conditions_data_path(self):
        self.data_set = [
            ([{'op': 'eq', 'field': 'data://memory_mb', 'value': 1024}],
             True),
            ([{'op': 'gt', 'field': 'data://local_gb', 'value': 42}],
             False)
        ]

        for condition, res in self.data_set:
            rule = rules.create(conditions_json=condition,
                                actions_json=self.actions_json)
            self.assertIs(res,
                          rule.check_conditions(self.node_info, self.data),
                          self.data)

    def test_conditions_node_path(self):
        self.node_set = [
            ([{'op': 'eq', 'field': 'node://driver_info.ipmi_address',
               'value': self.bmc_address}],
             True),
            ([{'op': 'eq', 'field': 'node://driver', 'value': 'fake'}],
             False)
        ]

        for condition, res in self.node_set:
            rule = rules.create(conditions_json=condition,
                                actions_json=self.actions_json)
            self.assertIs(res,
                          rule.check_conditions(self.node_info, self.data))


@mock.patch.object(plugins_base, 'rule_actions_manager', autospec=True)
class TestApplyActions(BaseTest):
    def setUp(self):
        super(TestApplyActions, self).setUp()
        self.actions_json.append({'action': 'example'})

        self.rule = rules.create(conditions_json=self.conditions_json,
                                 actions_json=self.actions_json)
        self.act_mock = mock.Mock(spec=plugins_base.RuleActionPlugin)
        self.act_mock.FORMATTED_PARAMS = ['value']
        self.ext_mock = mock.Mock(spec=['obj'], obj=self.act_mock)

    def test_apply(self, mock_ext_mgr):
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.rule.apply_actions(self.node_info, data=self.data)

        self.act_mock.apply.assert_any_call(self.node_info,
                                            {'message': 'boom!'})
        self.act_mock.apply.assert_any_call(self.node_info, {})
        self.assertEqual(len(self.actions_json),
                         self.act_mock.apply.call_count)

    def test_apply_data_format_value(self, mock_ext_mgr):
        self.rule = rules.create(actions_json=[
            {'action': 'set-attribute',
             'path': '/driver_info/ipmi_address',
             'value': '{data[memory_mb]}'}],
            conditions_json=self.conditions_json
        )
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.rule.apply_actions(self.node_info, data=self.data)

        self.assertEqual(1, self.act_mock.apply.call_count)

    def test_apply_data_format_value_dict(self, mock_ext_mgr):
        self.data.update({'val_outer': {'val_inner': 17},
                          'key_outer': {'key_inner': 'baz'}})

        self.rule = rules.create(actions_json=[
            {'action': 'set-attribute',
             'path': '/driver_info/foo',
             'value': {'{data[key_outer][key_inner]}':
                       '{data[val_outer][val_inner]}'}}],
            conditions_json=self.conditions_json
        )
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.rule.apply_actions(self.node_info, data=self.data)

        self.act_mock.apply.assert_called_once_with(self.node_info, {
            # String-formatted values will be coerced to be strings.
            'value': {'baz': '17'},
            'path': '/driver_info/foo'
        })

    def test_apply_data_format_value_list(self, mock_ext_mgr):
        self.data.update({'outer': {'inner': 'baz'}})

        self.rule = rules.create(actions_json=[
            {'action': 'set-attribute',
             'path': '/driver_info/foo',
             'value': ['basic', ['{data[outer][inner]}']]}],
            conditions_json=self.conditions_json
        )
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.rule.apply_actions(self.node_info, data=self.data)

        self.act_mock.apply.assert_called_once_with(self.node_info, {
            'value': ['basic', ['baz']],
            'path': '/driver_info/foo'
        })

    def test_apply_data_format_value_primitives(self, mock_ext_mgr):
        self.data.update({'outer': {'inner': False}})

        self.rule = rules.create(actions_json=[
            {'action': 'set-attribute',
             'path': '/driver_info/foo',
             'value': {42: {True: [3.14, 'foo', '{data[outer][inner]}']}}}],
            conditions_json=self.conditions_json
        )
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.rule.apply_actions(self.node_info, data=self.data)

        self.act_mock.apply.assert_called_once_with(self.node_info, {
            # String-formatted values will be coerced to be strings.
            'value': {42: {True: [3.14, 'foo', 'False']}},
            'path': '/driver_info/foo'
        })

    def test_apply_data_format_value_fail(self, mock_ext_mgr):
        self.rule = rules.create(
            actions_json=[
                {'action': 'set-attribute',
                 'path': '/driver_info/ipmi_address',
                 'value': '{data[inventory][bmc_address]}'}],
            conditions_json=self.conditions_json
        )
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.assertRaises(utils.Error, self.rule.apply_actions,
                          self.node_info, data=self.data)

    def test_apply_data_format_value_nested_fail(self, mock_ext_mgr):
        self.data.update({'outer': {'inner': 'baz'}})
        self.rule = rules.create(actions_json=[
            {'action': 'set-attribute',
             'path': '/driver_info/foo',
             'value': ['basic', ['{data[outer][nonexistent]}']]}],
            conditions_json=self.conditions_json
        )
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.assertRaises(utils.Error, self.rule.apply_actions,
                          self.node_info, data=self.data)

    def test_apply_data_non_format_value(self, mock_ext_mgr):
        self.rule = rules.create(actions_json=[
            {'action': 'set-attribute',
             'path': '/driver_info/ipmi_address',
             'value': 1}],
            conditions_json=self.conditions_json
        )
        mock_ext_mgr.return_value.__getitem__.return_value = self.ext_mock

        self.rule.apply_actions(self.node_info, data=self.data)

        self.assertEqual(1, self.act_mock.apply.call_count)


@mock.patch.object(rules, 'get_all', autospec=True)
class TestApply(BaseTest):
    def setUp(self):
        super(TestApply, self).setUp()
        self.rules = [mock.Mock(spec=rules.IntrospectionRule),
                      mock.Mock(spec=rules.IntrospectionRule)]

    def test_no_rules(self, mock_get_all):
        mock_get_all.return_value = []

        rules.apply(self.node_info, self.data)

    def test_apply(self, mock_get_all):
        mock_get_all.return_value = self.rules
        for idx, rule in enumerate(self.rules):
            rule.check_conditions.return_value = not bool(idx)

        rules.apply(self.node_info, self.data)

        for idx, rule in enumerate(self.rules):
            rule.check_conditions.assert_called_once_with(self.node_info,
                                                          self.data)
            if rule.check_conditions.return_value:
                rule.apply_actions.assert_called_once_with(
                    self.node_info, data=self.data)
            else:
                self.assertFalse(rule.apply_actions.called)
