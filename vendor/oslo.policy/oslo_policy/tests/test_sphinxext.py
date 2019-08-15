# Copyright 2017 Red Hat, Inc.
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

import textwrap

from oslotest import base

from oslo_policy import policy
from oslo_policy import sphinxext


class FormatPolicyTest(base.BaseTestCase):

    def test_minimal(self):
        results = '\n'.join(list(sphinxext._format_policy_section(
            'foo', [policy.RuleDefault('rule_a', '@')])))

        self.assertEqual(textwrap.dedent("""
        foo
        ===

        ``rule_a``
            :Default: ``@``

            (no description provided)
        """).lstrip(), results)

    def test_with_description(self):
        results = '\n'.join(list(sphinxext._format_policy_section(
            'foo', [policy.RuleDefault('rule_a', '@', 'My sample rule')]
        )))

        self.assertEqual(textwrap.dedent("""
        foo
        ===

        ``rule_a``
            :Default: ``@``

            My sample rule
        """).lstrip(), results)

    def test_with_operations(self):
        results = '\n'.join(list(sphinxext._format_policy_section(
            'foo', [policy.DocumentedRuleDefault(
                'rule_a', '@', 'My sample rule', [
                    {'method': 'GET', 'path': '/foo'},
                    {'method': 'POST', 'path': '/some'}])]
        )))

        self.assertEqual(textwrap.dedent("""
        foo
        ===

        ``rule_a``
            :Default: ``@``
            :Operations:
                - **GET** ``/foo``
                - **POST** ``/some``

            My sample rule
        """).lstrip(), results)

    def test_with_scope_types(self):
        operations = [
            {'method': 'GET', 'path': '/foo'},
            {'method': 'POST', 'path': '/some'}
        ]
        scope_types = ['bar']
        rule = policy.DocumentedRuleDefault(
            'rule_a', '@', 'My sample rule', operations,
            scope_types=scope_types
        )

        results = '\n'.join(list(sphinxext._format_policy_section(
            'foo', [rule]
        )))

        self.assertEqual(textwrap.dedent("""
        foo
        ===

        ``rule_a``
            :Default: ``@``
            :Operations:
                - **GET** ``/foo``
                - **POST** ``/some``
            :Scope Types:
                - **bar**

            My sample rule
        """).lstrip(), results)
