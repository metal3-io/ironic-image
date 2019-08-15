#    Copyright 2011 Justin Santa Barbara
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

from oslo_versionedobjects import exception
from oslo_versionedobjects import test

import mock


notifier = mock.Mock()


class TestWrapper(object):
    @exception.wrap_exception(notifier=notifier)
    def raise_exc(self, context, exc, admin_password):
        raise exc


class ExceptionTestCase(test.TestCase):
    def test_wrap_exception_wrapped(self):
        test = TestWrapper()
        # Ensure that the original function is available in
        # the __wrapped__ attribute
        self.assertTrue(hasattr(test.raise_exc, '__wrapped__'))

    def test_wrap_exception(self):
        context = "context"
        exc = ValueError()

        test = TestWrapper()
        notifier.reset_mock()

        # wrap_exception() must reraise the exception
        self.assertRaises(ValueError,
                          test.raise_exc, context, exc, admin_password="xxx")

        # wrap_exception() strips admin_password from args
        payload = {'args': {'self': test, 'context': context, 'exc': exc},
                   'exception': exc}
        notifier.error.assert_called_once_with(context, 'raise_exc', payload)

    def test_vo_exception(self):
        exc = exception.VersionedObjectsException()
        self.assertEqual('An unknown exception occurred.', str(exc))
        self.assertEqual({'code': 500}, exc.kwargs)

    def test_object_action_error(self):
        exc = exception.ObjectActionError(action='ACTION', reason='REASON',
                                          code=123)
        self.assertEqual('Object action ACTION failed because: REASON',
                         str(exc))
        self.assertEqual({'code': 123, 'action': 'ACTION', 'reason': 'REASON'},
                         exc.kwargs)

    def test_constructor_format_error(self):
        # Test error handling on formatting exception message in the
        # VersionedObjectsException constructor
        with mock.patch.object(exception, 'LOG') as log:
            exc = exception.ObjectActionError()

            log.error.assert_called_with('code: 500')

        # Formatting failed: the message is the original format string
        self.assertEqual(exception.ObjectActionError.msg_fmt, str(exc))
