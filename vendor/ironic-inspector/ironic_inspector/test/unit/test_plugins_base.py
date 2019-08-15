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

import collections

import mock

from ironic_inspector.plugins import base
from ironic_inspector.test import base as test_base


class WithValidation(base.WithValidation):
    REQUIRED_PARAMS = {'x'}
    OPTIONAL_PARAMS = {'y', 'z'}


class TestWithValidation(test_base.BaseTest):
    def setUp(self):
        super(TestWithValidation, self).setUp()
        self.test = WithValidation()

    def test_ok(self):
        for x in (1, 0, '', False, True):
            self.test.validate({'x': x})
        self.test.validate({'x': 'x', 'y': 42})
        self.test.validate({'x': 'x', 'y': 42, 'z': False})

    def test_required_missing(self):
        err_re = r'missing required parameter\(s\): x'
        self.assertRaisesRegex(ValueError, err_re, self.test.validate, {})
        self.assertRaisesRegex(ValueError, err_re, self.test.validate,
                               {'x': None})
        self.assertRaisesRegex(ValueError, err_re, self.test.validate,
                               {'y': 1, 'z': 2})

    def test_unexpected(self):
        self.assertRaisesRegex(ValueError, r'unexpected parameter\(s\): foo',
                               self.test.validate, {'foo': 'bar', 'x': 42})


fake_ext = collections.namedtuple('Extension', ['name', 'obj'])


@mock.patch.object(base, 'processing_hooks_manager', autospec=True)
class TestValidateProcessingHooks(test_base.BaseTest):
    def test_ok(self, mock_mgr):
        mock_mgr.return_value = [
            fake_ext(name='1', obj=mock.Mock(dependencies=[])),
            fake_ext(name='2', obj=mock.Mock(dependencies=['1'])),
            fake_ext(name='3', obj=mock.Mock(dependencies=['2', '1'])),
        ]

        hooks = base.validate_processing_hooks()
        self.assertEqual(mock_mgr.return_value, hooks)
        mock_mgr.assert_called_once_with()

    def test_broken_dependencies(self, mock_mgr):
        mock_mgr.return_value = [
            fake_ext(name='2', obj=mock.Mock(dependencies=['1'])),
            fake_ext(name='3', obj=mock.Mock(dependencies=['2', '1'])),
        ]

        self.assertRaisesRegex(RuntimeError, "missing: 1",
                               base.validate_processing_hooks)

    def test_self_dependency(self, mock_mgr):
        mock_mgr.return_value = [
            fake_ext(name='1', obj=mock.Mock(dependencies=['1'])),
        ]

        self.assertRaisesRegex(RuntimeError, "missing: 1",
                               base.validate_processing_hooks)

    def test_wrong_dependencies_order(self, mock_mgr):
        mock_mgr.return_value = [
            fake_ext(name='2', obj=mock.Mock(dependencies=['1'])),
            fake_ext(name='1', obj=mock.Mock(dependencies=[])),
            fake_ext(name='3', obj=mock.Mock(dependencies=['2', '1'])),
        ]

        self.assertRaisesRegex(RuntimeError, "missing: 1",
                               base.validate_processing_hooks)
