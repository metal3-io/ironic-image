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

import flask
import mock
from oslo_config import cfg
from oslo_utils import uuidutils
import six

from ironic_inspector import api_tools
import ironic_inspector.test.base as test_base
from ironic_inspector import utils

CONF = cfg.CONF
app = flask.Flask(__name__)
app.testing = True


def mock_test_field(return_value=None, side_effect=None):
    """Mock flask.request.args.get"""
    def outer(func):
        @six.wraps(func)
        def inner(self, *args, **kwargs):
            with app.test_request_context('/'):
                get_mock = flask.request.args.get = mock.Mock()
                get_mock.return_value = return_value
                get_mock.side_effect = side_effect
                ret = func(self, get_mock, *args, **kwargs)
            return ret
        return inner
    return outer


class RaisesCoercionExceptionTestCase(test_base.BaseTest):
    def test_ok(self):
        @api_tools.raises_coercion_exceptions
        def fn():
            return True
        self.assertIs(True, fn())

    def test_assertion_error(self):
        @api_tools.raises_coercion_exceptions
        def fn():
            assert False, 'Oops!'

        six.assertRaisesRegex(self, utils.Error, 'Bad request: Oops!', fn)

    def test_value_error(self):
        @api_tools.raises_coercion_exceptions
        def fn():
            raise ValueError('Oops!')

        six.assertRaisesRegex(self, utils.Error, 'Bad request: Oops!', fn)


class RequestFieldTestCase(test_base.BaseTest):
    @mock_test_field(return_value='42')
    def test_request_field_ok(self, get_mock):
        @api_tools.request_field('foo')
        def fn(value):
            self.assertEqual(get_mock.return_value, value)

        fn()
        get_mock.assert_called_once_with('foo', default=None)

    @mock_test_field(return_value='42')
    def test_request_field_with_default(self, get_mock):
        @api_tools.request_field('foo')
        def fn(value):
            self.assertEqual(get_mock.return_value, value)

        fn(default='bar')
        get_mock.assert_called_once_with('foo', default='bar')

    @mock_test_field(return_value=42)
    def test_request_field_with_default_returns_default(self, get_mock):
        @api_tools.request_field('foo')
        def fn(value):
            self.assertEqual(get_mock.return_value, value)

        fn(default=42)
        get_mock.assert_called_once_with('foo', default=42)


class MarkerFieldTestCase(test_base.BaseTest):
    @mock_test_field(return_value=uuidutils.generate_uuid())
    def test_marker_ok(self, get_mock):
        value = api_tools.marker_field()
        self.assertEqual(get_mock.return_value, value)

    @mock.patch.object(uuidutils, 'is_uuid_like', autospec=True)
    @mock_test_field(return_value='foo')
    def test_marker_check_fails(self, get_mock, like_mock):
        like_mock.return_value = False
        six.assertRaisesRegex(self, utils.Error, '.*(Marker not UUID-like)',
                              api_tools.marker_field)
        like_mock.assert_called_once_with(get_mock.return_value)


class LimitFieldTestCase(test_base.BaseTest):
    @mock_test_field(return_value=42)
    def test_limit_ok(self, get_mock):
        value = api_tools.limit_field()
        self.assertEqual(get_mock.return_value, value)

    @mock_test_field(return_value=str(CONF.api_max_limit + 1))
    def test_limit_over(self, get_mock):
        six.assertRaisesRegex(self, utils.Error,
                              '.*(Limit over %s)' % CONF.api_max_limit,
                              api_tools.limit_field)

    @mock_test_field(return_value='0')
    def test_limit_zero(self, get_mock):
        value = api_tools.limit_field()
        self.assertEqual(CONF.api_max_limit, value)

    @mock_test_field(return_value='-1')
    def test_limit_negative(self, get_mock):
        six.assertRaisesRegex(self, utils.Error,
                              '.*(Limit cannot be negative)',
                              api_tools.limit_field)

    @mock_test_field(return_value='foo')
    def test_limit_invalid_value(self, get_mock):
        six.assertRaisesRegex(self, utils.Error, 'Bad request',
                              api_tools.limit_field)
