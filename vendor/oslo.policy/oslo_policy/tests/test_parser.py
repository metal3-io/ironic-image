# Copyright (c) 2015 OpenStack Foundation.
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

import mock
from oslotest import base as test_base
import six

from oslo_policy import _checks
from oslo_policy import _parser
from oslo_policy.tests import base


class ParseCheckTestCase(test_base.BaseTestCase):
    def test_false(self):
        result = _parser._parse_check('!')

        self.assertIsInstance(result, _checks.FalseCheck)

    def test_true(self):
        result = _parser._parse_check('@')

        self.assertIsInstance(result, _checks.TrueCheck)

    def test_bad_rule(self):
        result = _parser._parse_check('foobar')

        self.assertIsInstance(result, _checks.FalseCheck)

    @mock.patch.object(_checks, 'registered_checks', {})
    def test_no_handler(self):
        result = _parser._parse_check('no:handler')

        self.assertIsInstance(result, _checks.FalseCheck)

    @mock.patch.object(_checks, 'registered_checks', {
        'spam': mock.Mock(return_value='spam_check'),
        None: mock.Mock(return_value='none_check'),
    })
    def test_check(self):
        result = _parser._parse_check('spam:handler')

        self.assertEqual('spam_check', result)
        _checks.registered_checks['spam'].assert_called_once_with('spam',
                                                                  'handler')
        self.assertFalse(_checks.registered_checks[None].called)

    @mock.patch.object(_checks, 'registered_checks', {
        None: mock.Mock(return_value='none_check'),
    })
    def test_check_default(self):
        result = _parser._parse_check('spam:handler')

        self.assertEqual('none_check', result)
        _checks.registered_checks[None].assert_called_once_with('spam',
                                                                'handler')


class ParseListRuleTestCase(test_base.BaseTestCase):
    def test_empty(self):
        result = _parser._parse_list_rule([])

        self.assertIsInstance(result, _checks.TrueCheck)
        self.assertEqual('@', str(result))

    @mock.patch.object(_parser, '_parse_check', base.FakeCheck)
    def test_oneele_zeroele(self):
        result = _parser._parse_list_rule([[]])

        self.assertIsInstance(result, _checks.FalseCheck)
        self.assertEqual('!', str(result))

    @mock.patch.object(_parser, '_parse_check', base.FakeCheck)
    def test_oneele_bare(self):
        result = _parser._parse_list_rule(['rule'])

        self.assertIsInstance(result, base.FakeCheck)
        self.assertEqual('rule', result.result)
        self.assertEqual('rule', str(result))

    @mock.patch.object(_parser, '_parse_check', base.FakeCheck)
    def test_oneele_oneele(self):
        result = _parser._parse_list_rule([['rule']])

        self.assertIsInstance(result, base.FakeCheck)
        self.assertEqual('rule', result.result)
        self.assertEqual('rule', str(result))

    @mock.patch.object(_parser, '_parse_check', base.FakeCheck)
    def test_oneele_multi(self):
        result = _parser._parse_list_rule([['rule1', 'rule2']])

        self.assertIsInstance(result, _checks.AndCheck)
        self.assertEqual(2, len(result.rules))
        for i, value in enumerate(['rule1', 'rule2']):
            self.assertIsInstance(result.rules[i], base.FakeCheck)
            self.assertEqual(value, result.rules[i].result)
        self.assertEqual('(rule1 and rule2)', str(result))

    @mock.patch.object(_parser, '_parse_check', base.FakeCheck)
    def test_multi_oneele(self):
        result = _parser._parse_list_rule([['rule1'], ['rule2']])

        self.assertIsInstance(result, _checks.OrCheck)
        self.assertEqual(2, len(result.rules))
        for i, value in enumerate(['rule1', 'rule2']):
            self.assertIsInstance(result.rules[i], base.FakeCheck)
            self.assertEqual(value, result.rules[i].result)
        self.assertEqual('(rule1 or rule2)', str(result))

    @mock.patch.object(_parser, '_parse_check', base.FakeCheck)
    def test_multi_multi(self):
        result = _parser._parse_list_rule([['rule1', 'rule2'],
                                          ['rule3', 'rule4']])

        self.assertIsInstance(result, _checks.OrCheck)
        self.assertEqual(2, len(result.rules))
        for i, values in enumerate([['rule1', 'rule2'], ['rule3', 'rule4']]):
            self.assertIsInstance(result.rules[i], _checks.AndCheck)
            self.assertEqual(2, len(result.rules[i].rules))
            for j, value in enumerate(values):
                self.assertIsInstance(result.rules[i].rules[j],
                                      base.FakeCheck)
                self.assertEqual(value, result.rules[i].rules[j].result)
        self.assertEqual('((rule1 and rule2) or (rule3 and rule4))',
                         str(result))


class ParseTokenizeTestCase(test_base.BaseTestCase):
    @mock.patch.object(_parser, '_parse_check', lambda x: x)
    def test_tokenize(self):
        exemplar = ("(( ( ((() And)) or ) (check:%(miss)s) not)) "
                    "'a-string' \"another-string\"")
        expected = [
            ('(', '('), ('(', '('), ('(', '('), ('(', '('), ('(', '('),
            ('(', '('), (')', ')'), ('and', 'And'),
            (')', ')'), (')', ')'), ('or', 'or'), (')', ')'), ('(', '('),
            ('check', 'check:%(miss)s'), (')', ')'), ('not', 'not'),
            (')', ')'), (')', ')'),
            ('string', 'a-string'),
            ('string', 'another-string'),
        ]

        result = list(_parser._parse_tokenize(exemplar))

        self.assertEqual(expected, result)


class ParseStateMetaTestCase(test_base.BaseTestCase):
    def test_reducer(self):
        @_parser.reducer('a', 'b', 'c')
        @_parser.reducer('d', 'e', 'f')
        def spam():
            pass

        self.assertTrue(hasattr(spam, 'reducers'))
        self.assertEqual([['d', 'e', 'f'], ['a', 'b', 'c']], spam.reducers)

    def test_parse_state_meta(self):
        @six.add_metaclass(_parser.ParseStateMeta)
        class FakeState(object):

            @_parser.reducer('a', 'b', 'c')
            @_parser.reducer('d', 'e', 'f')
            def reduce1(self):
                pass

            @_parser.reducer('g', 'h', 'i')
            def reduce2(self):
                pass

        self.assertTrue(hasattr(FakeState, 'reducers'))
        for reduction, reducer in FakeState.reducers:
            if (reduction == ['a', 'b', 'c'] or
                    reduction == ['d', 'e', 'f']):
                self.assertEqual('reduce1', reducer)
            elif reduction == ['g', 'h', 'i']:
                self.assertEqual('reduce2', reducer)
            else:
                self.fail('Unrecognized reducer discovered')


class ParseStateTestCase(test_base.BaseTestCase):
    def test_init(self):
        state = _parser.ParseState()

        self.assertEqual([], state.tokens)
        self.assertEqual([], state.values)

    @mock.patch.object(_parser.ParseState, 'reducers', [(['tok1'], 'meth')])
    @mock.patch.object(_parser.ParseState, 'meth', create=True)
    def test_reduce_none(self, mock_meth):
        state = _parser.ParseState()
        state.tokens = ['tok2']
        state.values = ['val2']

        state.reduce()

        self.assertEqual(['tok2'], state.tokens)
        self.assertEqual(['val2'], state.values)
        self.assertFalse(mock_meth.called)

    @mock.patch.object(_parser.ParseState, 'reducers',
                       [(['tok1', 'tok2'], 'meth')])
    @mock.patch.object(_parser.ParseState, 'meth', create=True)
    def test_reduce_short(self, mock_meth):
        state = _parser.ParseState()
        state.tokens = ['tok1']
        state.values = ['val1']

        state.reduce()

        self.assertEqual(['tok1'], state.tokens)
        self.assertEqual(['val1'], state.values)
        self.assertFalse(mock_meth.called)

    @mock.patch.object(_parser.ParseState, 'reducers',
                       [(['tok1', 'tok2'], 'meth')])
    @mock.patch.object(_parser.ParseState, 'meth', create=True,
                       return_value=[('tok3', 'val3')])
    def test_reduce_one(self, mock_meth):
        state = _parser.ParseState()
        state.tokens = ['tok1', 'tok2']
        state.values = ['val1', 'val2']

        state.reduce()

        self.assertEqual(['tok3'], state.tokens)
        self.assertEqual(['val3'], state.values)
        mock_meth.assert_called_once_with('val1', 'val2')

    @mock.patch.object(_parser.ParseState, 'reducers', [
        (['tok1', 'tok4'], 'meth2'),
        (['tok2', 'tok3'], 'meth1'),
    ])
    @mock.patch.object(_parser.ParseState, 'meth1', create=True,
                       return_value=[('tok4', 'val4')])
    @mock.patch.object(_parser.ParseState, 'meth2', create=True,
                       return_value=[('tok5', 'val5')])
    def test_reduce_two(self, mock_meth2, mock_meth1):
        state = _parser.ParseState()
        state.tokens = ['tok1', 'tok2', 'tok3']
        state.values = ['val1', 'val2', 'val3']

        state.reduce()

        self.assertEqual(['tok5'], state.tokens)
        self.assertEqual(['val5'], state.values)
        mock_meth1.assert_called_once_with('val2', 'val3')
        mock_meth2.assert_called_once_with('val1', 'val4')

    @mock.patch.object(_parser.ParseState, 'reducers',
                       [(['tok1', 'tok2'], 'meth')])
    @mock.patch.object(_parser.ParseState, 'meth', create=True,
                       return_value=[('tok3', 'val3'), ('tok4', 'val4')])
    def test_reduce_multi(self, mock_meth):
        state = _parser.ParseState()
        state.tokens = ['tok1', 'tok2']
        state.values = ['val1', 'val2']

        state.reduce()

        self.assertEqual(['tok3', 'tok4'], state.tokens)
        self.assertEqual(['val3', 'val4'], state.values)
        mock_meth.assert_called_once_with('val1', 'val2')

    def test_shift(self):
        state = _parser.ParseState()

        with mock.patch.object(_parser.ParseState, 'reduce') as mock_reduce:
            state.shift('token', 'value')

            self.assertEqual(['token'], state.tokens)
            self.assertEqual(['value'], state.values)
            mock_reduce.assert_called_once_with()

    def test_result_empty(self):
        state = _parser.ParseState()

        self.assertRaises(ValueError, lambda: state.result)

    def test_result_unreduced(self):
        state = _parser.ParseState()
        state.tokens = ['tok1', 'tok2']
        state.values = ['val1', 'val2']

        self.assertRaises(ValueError, lambda: state.result)

    def test_result(self):
        state = _parser.ParseState()
        state.tokens = ['token']
        state.values = ['value']

        self.assertEqual('value', state.result)

    def test_wrap_check(self):
        state = _parser.ParseState()

        result = state._wrap_check('(', 'the_check', ')')

        self.assertEqual([('check', 'the_check')], result)

    @mock.patch.object(_checks, 'AndCheck', lambda x: x)
    def test_make_and_expr(self):
        state = _parser.ParseState()

        result = state._make_and_expr('check1', 'and', 'check2')

        self.assertEqual([('and_expr', ['check1', 'check2'])], result)

    def test_extend_and_expr(self):
        state = _parser.ParseState()
        mock_expr = mock.Mock()
        mock_expr.add_check.return_value = 'newcheck'

        result = state._extend_and_expr(mock_expr, 'and', 'check')

        self.assertEqual([('and_expr', 'newcheck')], result)
        mock_expr.add_check.assert_called_once_with('check')

    @mock.patch.object(_checks, 'OrCheck', lambda x: x)
    def test_make_or_expr(self):
        state = _parser.ParseState()

        result = state._make_or_expr('check1', 'or', 'check2')

        self.assertEqual([('or_expr', ['check1', 'check2'])], result)

    def test_extend_or_expr(self):
        state = _parser.ParseState()
        mock_expr = mock.Mock()
        mock_expr.add_check.return_value = 'newcheck'

        result = state._extend_or_expr(mock_expr, 'or', 'check')

        self.assertEqual([('or_expr', 'newcheck')], result)
        mock_expr.add_check.assert_called_once_with('check')

    @mock.patch.object(_checks, 'NotCheck', lambda x: 'not %s' % x)
    def test_make_not_expr(self):
        state = _parser.ParseState()

        result = state._make_not_expr('not', 'check')

        self.assertEqual([('check', 'not check')], result)


class ParseTextRuleTestCase(test_base.BaseTestCase):
    def test_empty(self):
        result = _parser._parse_text_rule('')

        self.assertIsInstance(result, _checks.TrueCheck)

    @mock.patch.object(_parser, '_parse_tokenize',
                       return_value=[('tok1', 'val1'), ('tok2', 'val2')])
    @mock.patch.object(_parser.ParseState, 'shift')
    @mock.patch.object(_parser.ParseState, 'result', 'result')
    def test_shifts(self, mock_shift, mock_parse_tokenize):
        result = _parser._parse_text_rule('test rule')

        self.assertEqual('result', result)
        mock_parse_tokenize.assert_called_once_with('test rule')
        mock_shift.assert_has_calls(
            [mock.call('tok1', 'val1'), mock.call('tok2', 'val2')])

    @mock.patch.object(_parser, '_parse_tokenize', return_value=[])
    def test_fail(self, mock_parse_tokenize):
        result = _parser._parse_text_rule('test rule')

        self.assertIsInstance(result, _checks.FalseCheck)
        mock_parse_tokenize.assert_called_once_with('test rule')

    def test_A_or_B_or_C(self):
        result = _parser._parse_text_rule('@ or ! or @')
        self.assertEqual('(@ or ! or @)', str(result))

    def test_A_or_B_and_C(self):
        result = _parser._parse_text_rule('@ or ! and @')
        self.assertEqual('(@ or (! and @))', str(result))

    def test_A_and_B_or_C(self):
        result = _parser._parse_text_rule('@ and ! or @')
        self.assertEqual('((@ and !) or @)', str(result))

    def test_A_and_B_and_C(self):
        result = _parser._parse_text_rule('@ and ! and @')
        self.assertEqual('(@ and ! and @)', str(result))

    def test_A_or_B_or_C_or_D(self):
        result = _parser._parse_text_rule('@ or ! or @ or !')
        self.assertEqual('(@ or ! or @ or !)', str(result))

    def test_A_or_B_or_C_and_D(self):
        result = _parser._parse_text_rule('@ or ! or @ and !')
        self.assertEqual('(@ or ! or (@ and !))', str(result))

    def test_A_or_B_and_C_or_D(self):
        result = _parser._parse_text_rule('@ or ! and @ or !')
        self.assertEqual('(@ or (! and @) or !)', str(result))

    def test_A_or_B_and_C_and_D(self):
        result = _parser._parse_text_rule('@ or ! and @ and !')
        self.assertEqual('(@ or (! and @ and !))', str(result))

    def test_A_and_B_or_C_or_D(self):
        result = _parser._parse_text_rule('@ and ! or @ or !')
        self.assertEqual('((@ and !) or @ or !)', str(result))

    def test_A_and_B_or_C_and_D(self):
        result = _parser._parse_text_rule('@ and ! or @ and !')
        self.assertEqual('((@ and !) or (@ and !))', str(result))

    def test_A_and_B_and_C_or_D(self):
        result = _parser._parse_text_rule('@ and ! and @ or !')
        self.assertEqual('((@ and ! and @) or !)', str(result))

    def test_A_and_B_and_C_and_D(self):
        result = _parser._parse_text_rule('@ and ! and @ and !')
        self.assertEqual('(@ and ! and @ and !)', str(result))

    def test_A_and_B_or_C_with_not_1(self):
        result = _parser._parse_text_rule('not @ and ! or @')
        self.assertEqual('((not @ and !) or @)', str(result))

    def test_A_and_B_or_C_with_not_2(self):
        result = _parser._parse_text_rule('@ and not ! or @')
        self.assertEqual('((@ and not !) or @)', str(result))

    def test_A_and_B_or_C_with_not_3(self):
        result = _parser._parse_text_rule('@ and ! or not @')
        self.assertEqual('((@ and !) or not @)', str(result))

    def test_A_and_B_or_C_with_group_1(self):
        for expression in ['( @ ) and ! or @',
                           '@ and ( ! ) or @',
                           '@ and ! or ( @ )',
                           '( @ ) and ! or ( @ )',
                           '@ and ( ! ) or ( @ )',
                           '( @ ) and ( ! ) or ( @ )',
                           '( @ and ! ) or @',
                           '( ( @ ) and ! ) or @',
                           '( @ and ( ! ) ) or @',
                           '( ( @ and ! ) ) or @',
                           '( @ and ! or @ )']:
            result = _parser._parse_text_rule(expression)
            self.assertEqual('((@ and !) or @)', str(result))

    def test_A_and_B_or_C_with_group_2(self):
        result = _parser._parse_text_rule('@ and ( ! or @ )')
        self.assertEqual('(@ and (! or @))', str(result))

    def test_A_and_B_or_C_with_group_and_not_1(self):
        for expression in ['not ( @ ) and ! or @',
                           'not @ and ( ! ) or @',
                           'not @ and ! or ( @ )',
                           '( not @ ) and ! or @',
                           '( not @ and ! ) or @',
                           '( not @ and ! or @ )']:
            result = _parser._parse_text_rule(expression)
            self.assertEqual('((not @ and !) or @)', str(result))

    def test_A_and_B_or_C_with_group_and_not_2(self):
        result = _parser._parse_text_rule('not @ and ( ! or @ )')
        self.assertEqual('(not @ and (! or @))', str(result))

    def test_A_and_B_or_C_with_group_and_not_3(self):
        result = _parser._parse_text_rule('not ( @ and ! or @ )')
        self.assertEqual('not ((@ and !) or @)', str(result))

    def test_A_and_B_or_C_with_group_and_not_4(self):
        for expression in ['( @ ) and not ! or @',
                           '@ and ( not ! ) or @',
                           '@ and not ( ! ) or @',
                           '@ and not ! or ( @ )',
                           '( @ and not ! ) or @',
                           '( @ and not ! or @ )']:
            result = _parser._parse_text_rule(expression)
            self.assertEqual('((@ and not !) or @)', str(result))

    def test_A_and_B_or_C_with_group_and_not_5(self):
        result = _parser._parse_text_rule('@ and ( not ! or @ )')
        self.assertEqual('(@ and (not ! or @))', str(result))

    def test_A_and_B_or_C_with_group_and_not_6(self):
        result = _parser._parse_text_rule('@ and not ( ! or @ )')
        self.assertEqual('(@ and not (! or @))', str(result))

    def test_A_and_B_or_C_with_group_and_not_7(self):
        for expression in ['( @ ) and ! or not @',
                           '@ and ( ! ) or not @',
                           '@ and ! or not ( @ )',
                           '@ and ! or ( not @ )',
                           '( @ and ! ) or not @',
                           '( @ and ! or not @ )']:
            result = _parser._parse_text_rule(expression)
            self.assertEqual('((@ and !) or not @)', str(result))

    def test_A_and_B_or_C_with_group_and_not_8(self):
        result = _parser._parse_text_rule('@ and ( ! or not @ )')
        self.assertEqual('(@ and (! or not @))', str(result))


class ParseRuleTestCase(test_base.BaseTestCase):
    @mock.patch.object(_parser, '_parse_text_rule', return_value='text rule')
    @mock.patch.object(_parser, '_parse_list_rule', return_value='list rule')
    def test_parse_rule_string(self, mock_parse_list_rule,
                               mock_parse_text_rule):
        result = _parser.parse_rule('a string')

        self.assertEqual('text rule', result)
        self.assertFalse(mock_parse_list_rule.called)
        mock_parse_text_rule.assert_called_once_with('a string')

    @mock.patch.object(_parser, '_parse_text_rule', return_value='text rule')
    @mock.patch.object(_parser, '_parse_list_rule', return_value='list rule')
    def test_parse_rule_list(self, mock_parse_list_rule, mock_parse_text_rule):
        result = _parser.parse_rule([['a'], ['list']])

        self.assertEqual('list rule', result)
        self.assertFalse(mock_parse_text_rule.called)
        mock_parse_list_rule.assert_called_once_with([['a'], ['list']])
