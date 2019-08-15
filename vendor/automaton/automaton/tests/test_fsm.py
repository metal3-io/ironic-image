#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
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

import collections
import functools
import random

from automaton import exceptions as excp
from automaton import machines
from automaton import runners

import six
from testtools import testcase


class FSMTest(testcase.TestCase):

    @staticmethod
    def _create_fsm(start_state, add_start=True, add_states=None):
        m = machines.FiniteMachine()
        if add_start:
            m.add_state(start_state)
            m.default_start_state = start_state
        if add_states:
            for s in add_states:
                if s in m:
                    continue
                m.add_state(s)
        return m

    def setUp(self):
        super(FSMTest, self).setUp()
        # NOTE(harlowja): this state machine will never stop if run() is used.
        self.jumper = self._create_fsm("down", add_states=['up', 'down'])
        self.jumper.add_transition('down', 'up', 'jump')
        self.jumper.add_transition('up', 'down', 'fall')
        self.jumper.add_reaction('up', 'jump', lambda *args: 'fall')
        self.jumper.add_reaction('down', 'fall', lambda *args: 'jump')

    def test_build(self):
        space = []
        for a in 'abc':
            space.append(machines.State(a))
        m = machines.FiniteMachine.build(space)
        for a in 'abc':
            self.assertIn(a, m)

    def test_build_transitions(self):
        space = [
            machines.State('down', is_terminal=False,
                           next_states={'jump': 'up'}),
            machines.State('up', is_terminal=False,
                           next_states={'fall': 'down'}),
        ]
        m = machines.FiniteMachine.build(space)
        m.default_start_state = 'down'
        expected = [('down', 'jump', 'up'), ('up', 'fall', 'down')]
        self.assertEqual(expected, list(m))

    def test_build_transitions_with_callbacks(self):
        entered = collections.defaultdict(list)
        exitted = collections.defaultdict(list)

        def on_enter(state, event):
            entered[state].append(event)

        def on_exit(state, event):
            exitted[state].append(event)

        space = [
            machines.State('down', is_terminal=False,
                           next_states={'jump': 'up'},
                           on_enter=on_enter, on_exit=on_exit),
            machines.State('up', is_terminal=False,
                           next_states={'fall': 'down'},
                           on_enter=on_enter, on_exit=on_exit),
        ]
        m = machines.FiniteMachine.build(space)
        m.default_start_state = 'down'
        expected = [('down', 'jump', 'up'), ('up', 'fall', 'down')]
        self.assertEqual(expected, list(m))

        m.initialize()
        m.process_event('jump')

        self.assertEqual({'down': ['jump']}, dict(exitted))
        self.assertEqual({'up': ['jump']}, dict(entered))

        m.process_event('fall')

        self.assertEqual({'down': ['jump'], 'up': ['fall']}, dict(exitted))
        self.assertEqual({'up': ['jump'], 'down': ['fall']}, dict(entered))

    def test_build_transitions_dct(self):
        space = [
            {
                'name': 'down', 'is_terminal': False,
                'next_states': {'jump': 'up'},
            },
            {
                'name': 'up', 'is_terminal': False,
                'next_states': {'fall': 'down'},
            },
        ]
        m = machines.FiniteMachine.build(space)
        m.default_start_state = 'down'
        expected = [('down', 'jump', 'up'), ('up', 'fall', 'down')]
        self.assertEqual(expected, list(m))

    def test_build_terminal(self):
        space = [
            machines.State('down', is_terminal=False,
                           next_states={'jump': 'fell_over'}),
            machines.State('fell_over', is_terminal=True),
        ]
        m = machines.FiniteMachine.build(space)
        m.default_start_state = 'down'
        m.initialize()
        m.process_event('jump')
        self.assertTrue(m.terminated)

    def test_actionable(self):
        self.jumper.initialize()
        self.assertTrue(self.jumper.is_actionable_event('jump'))
        self.assertFalse(self.jumper.is_actionable_event('fall'))

    def test_bad_start_state(self):
        m = self._create_fsm('unknown', add_start=False)
        r = runners.FiniteRunner(m)
        self.assertRaises(excp.NotFound, r.run, 'unknown')

    def test_contains(self):
        m = self._create_fsm('unknown', add_start=False)
        self.assertNotIn('unknown', m)
        m.add_state('unknown')
        self.assertIn('unknown', m)

    def test_no_add_transition_terminal(self):
        m = self._create_fsm('up')
        m.add_state('down', terminal=True)
        self.assertRaises(excp.InvalidState,
                          m.add_transition, 'down', 'up', 'jump')

    def test_duplicate_state(self):
        m = self._create_fsm('unknown')
        self.assertRaises(excp.Duplicate, m.add_state, 'unknown')

    def test_duplicate_transition(self):
        m = self.jumper
        m.add_state('side_ways')
        self.assertRaises(excp.Duplicate,
                          m.add_transition, 'up', 'side_ways', 'fall')

    def test_duplicate_transition_replace(self):
        m = self.jumper
        m.add_state('side_ways')
        m.add_transition('up', 'side_ways', 'fall', replace=True)

    def test_duplicate_transition_same_transition(self):
        m = self.jumper
        m.add_transition('up', 'down', 'fall')

    def test_duplicate_reaction(self):
        self.assertRaises(
            # Currently duplicate reactions are not allowed...
            excp.Duplicate,
            self.jumper.add_reaction, 'down', 'fall', lambda *args: 'skate')

    def test_bad_transition(self):
        m = self._create_fsm('unknown')
        m.add_state('fire')
        self.assertRaises(excp.NotFound, m.add_transition,
                          'unknown', 'something', 'boom')
        self.assertRaises(excp.NotFound, m.add_transition,
                          'something', 'unknown', 'boom')

    def test_bad_reaction(self):
        m = self._create_fsm('unknown')
        self.assertRaises(excp.NotFound, m.add_reaction, 'something', 'boom',
                          lambda *args: 'cough')

    def test_run(self):
        m = self._create_fsm('down', add_states=['up', 'down'])
        m.add_state('broken', terminal=True)
        m.add_transition('down', 'up', 'jump')
        m.add_transition('up', 'broken', 'hit-wall')
        m.add_reaction('up', 'jump', lambda *args: 'hit-wall')
        self.assertEqual(['broken', 'down', 'up'], sorted(m.states))
        self.assertEqual(2, m.events)
        m.initialize()
        self.assertEqual('down', m.current_state)
        self.assertFalse(m.terminated)
        r = runners.FiniteRunner(m)
        r.run('jump')
        self.assertTrue(m.terminated)
        self.assertEqual('broken', m.current_state)
        self.assertRaises(excp.InvalidState, r.run,
                          'jump', initialize=False)

    def test_on_enter_on_exit(self):
        enter_transitions = []
        exit_transitions = []

        def on_exit(state, event):
            exit_transitions.append((state, event))

        def on_enter(state, event):
            enter_transitions.append((state, event))

        m = self._create_fsm('start', add_start=False)
        m.add_state('start', on_exit=on_exit)
        m.add_state('down', on_enter=on_enter, on_exit=on_exit)
        m.add_state('up', on_enter=on_enter, on_exit=on_exit)
        m.add_transition('start', 'down', 'beat')
        m.add_transition('down', 'up', 'jump')
        m.add_transition('up', 'down', 'fall')

        m.initialize('start')
        m.process_event('beat')
        m.process_event('jump')
        m.process_event('fall')
        self.assertEqual([('down', 'beat'),
                          ('up', 'jump'), ('down', 'fall')], enter_transitions)
        self.assertEqual([('start', 'beat'), ('down', 'jump'), ('up', 'fall')],
                         exit_transitions)

    def test_run_iter(self):
        up_downs = []
        runner = runners.FiniteRunner(self.jumper)
        for (old_state, new_state) in runner.run_iter('jump'):
            up_downs.append((old_state, new_state))
            if len(up_downs) >= 3:
                break
        self.assertEqual([('down', 'up'), ('up', 'down'), ('down', 'up')],
                         up_downs)
        self.assertFalse(self.jumper.terminated)
        self.assertEqual('up', self.jumper.current_state)
        self.jumper.process_event('fall')
        self.assertEqual('down', self.jumper.current_state)

    def test_run_send(self):
        up_downs = []
        runner = runners.FiniteRunner(self.jumper)
        it = runner.run_iter('jump')
        while True:
            up_downs.append(it.send(None))
            if len(up_downs) >= 3:
                it.close()
                break
        self.assertEqual('up', self.jumper.current_state)
        self.assertFalse(self.jumper.terminated)
        self.assertEqual([('down', 'up'), ('up', 'down'), ('down', 'up')],
                         up_downs)
        self.assertRaises(StopIteration, six.next, it)

    def test_run_send_fail(self):
        up_downs = []
        runner = runners.FiniteRunner(self.jumper)
        it = runner.run_iter('jump')
        up_downs.append(six.next(it))
        self.assertRaises(excp.NotFound, it.send, 'fail')
        it.close()
        self.assertEqual([('down', 'up')], up_downs)

    def test_not_initialized(self):
        self.assertRaises(excp.NotInitialized,
                          self.jumper.process_event, 'jump')

    def test_copy_states(self):
        c = self._create_fsm('down', add_start=False)
        self.assertEqual(0, len(c.states))
        d = c.copy()
        c.add_state('up')
        c.add_state('down')
        self.assertEqual(2, len(c.states))
        self.assertEqual(0, len(d.states))

    def test_copy_reactions(self):
        c = self._create_fsm('down', add_start=False)
        d = c.copy()

        c.add_state('down')
        c.add_state('up')
        c.add_reaction('down', 'jump', lambda *args: 'up')
        c.add_transition('down', 'up', 'jump')

        self.assertEqual(1, c.events)
        self.assertEqual(0, d.events)
        self.assertNotIn('down', d)
        self.assertNotIn('up', d)
        self.assertEqual([], list(d))
        self.assertEqual([('down', 'jump', 'up')], list(c))

    def test_copy_initialized(self):
        j = self.jumper.copy()
        self.assertIsNone(j.current_state)
        r = runners.FiniteRunner(self.jumper)

        for i, transition in enumerate(r.run_iter('jump')):
            if i == 4:
                break

        self.assertIsNone(j.current_state)
        self.assertIsNotNone(self.jumper.current_state)

    def test_iter(self):
        transitions = list(self.jumper)
        self.assertEqual(2, len(transitions))
        self.assertIn(('up', 'fall', 'down'), transitions)
        self.assertIn(('down', 'jump', 'up'), transitions)

    def test_freeze(self):
        self.jumper.freeze()
        self.assertRaises(excp.FrozenMachine, self.jumper.add_state, 'test')
        self.assertRaises(excp.FrozenMachine,
                          self.jumper.add_transition, 'test', 'test', 'test')
        self.assertRaises(excp.FrozenMachine,
                          self.jumper.add_reaction,
                          'test', 'test', lambda *args: 'test')

    def test_freeze_copy_unfreeze(self):
        self.jumper.freeze()
        self.assertTrue(self.jumper.frozen)
        cp = self.jumper.copy(unfreeze=True)
        self.assertTrue(self.jumper.frozen)
        self.assertFalse(cp.frozen)

    def test_invalid_callbacks(self):
        m = self._create_fsm('working', add_states=['working', 'broken'])
        self.assertRaises(ValueError, m.add_state, 'b', on_enter=2)
        self.assertRaises(ValueError, m.add_state, 'b', on_exit=2)


class HFSMTest(FSMTest):

    @staticmethod
    def _create_fsm(start_state,
                    add_start=True, hierarchical=False, add_states=None):
        if hierarchical:
            m = machines.HierarchicalFiniteMachine()
        else:
            m = machines.FiniteMachine()
        if add_start:
            m.add_state(start_state)
            m.default_start_state = start_state
        if add_states:
            for s in add_states:
                if s not in m:
                    m.add_state(s)
        return m

    def _make_phone_call(self, talk_time=1.0):

        def phone_reaction(old_state, new_state, event, chat_iter):
            try:
                six.next(chat_iter)
            except StopIteration:
                return 'finish'
            else:
                # Talk until the iterator expires...
                return 'chat'

        talker = self._create_fsm("talk")
        talker.add_transition("talk", "talk", "pickup")
        talker.add_transition("talk", "talk", "chat")
        talker.add_reaction("talk", "pickup", lambda *args: 'chat')
        chat_iter = iter(list(range(0, 10)))
        talker.add_reaction("talk", "chat", phone_reaction, chat_iter)

        handler = self._create_fsm('begin', hierarchical=True)
        handler.add_state("phone", machine=talker)
        handler.add_state('hangup', terminal=True)
        handler.add_transition("begin", "phone", "call")
        handler.add_reaction("phone", 'call', lambda *args: 'pickup')
        handler.add_transition("phone", "hangup", "finish")

        return handler

    def _make_phone_dialer(self):
        dialer = self._create_fsm("idle", hierarchical=True)
        digits = self._create_fsm("idle")

        dialer.add_state("pickup", machine=digits)
        dialer.add_transition("idle", "pickup", "dial")
        dialer.add_reaction("pickup", "dial", lambda *args: 'press')
        dialer.add_state("hangup", terminal=True)

        def react_to_press(last_state, new_state, event, number_calling):
            if len(number_calling) >= 10:
                return 'call'
            else:
                return 'press'

        digit_maker = functools.partial(random.randint, 0, 9)
        number_calling = []
        digits.add_state(
            "accumulate",
            on_enter=lambda *args: number_calling.append(digit_maker()))
        digits.add_transition("idle", "accumulate", "press")
        digits.add_transition("accumulate", "accumulate", "press")
        digits.add_reaction("accumulate", "press",
                            react_to_press, number_calling)
        digits.add_state("dial", terminal=True)
        digits.add_transition("accumulate", "dial", "call")
        digits.add_reaction("dial", "call", lambda *args: 'ringing')
        dialer.add_state("talk")
        dialer.add_transition("pickup", "talk", "ringing")
        dialer.add_reaction("talk", "ringing", lambda *args: 'hangup')
        dialer.add_transition("talk", "hangup", 'hangup')
        return dialer, number_calling

    def test_nested_machines(self):
        dialer, _number_calling = self._make_phone_dialer()
        self.assertEqual(1, len(dialer.nested_machines))

    def test_nested_machine_initializers(self):
        dialer, _number_calling = self._make_phone_dialer()
        queried_for = []

        def init_with(nested_machine):
            queried_for.append(nested_machine)
            return None

        dialer.initialize(nested_start_state_fetcher=init_with)
        self.assertEqual(1, len(queried_for))

    def test_phone_dialer_iter(self):
        dialer, number_calling = self._make_phone_dialer()
        self.assertEqual(0, len(number_calling))
        r = runners.HierarchicalRunner(dialer)
        transitions = list(r.run_iter('dial'))
        self.assertEqual(('talk', 'hangup'), transitions[-1])
        self.assertEqual(len(number_calling),
                         sum(1 if new_state == 'accumulate' else 0
                         for (old_state, new_state) in transitions))
        self.assertEqual(10, len(number_calling))

    def test_phone_call(self):
        handler = self._make_phone_call()
        r = runners.HierarchicalRunner(handler)
        r.run('call')
        self.assertTrue(handler.terminated)

    def test_phone_call_iter(self):
        handler = self._make_phone_call()
        r = runners.HierarchicalRunner(handler)
        transitions = list(r.run_iter('call'))
        self.assertEqual(('talk', 'hangup'), transitions[-1])
        self.assertEqual(("begin", 'phone'), transitions[0])
        talk_talk = 0
        for transition in transitions:
            if transition == ("talk", "talk"):
                talk_talk += 1
        self.assertGreater(talk_talk, 0)
