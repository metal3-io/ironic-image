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

import sys
import time
import uuid
import warnings

import fixtures
import mock
from oslo_log import log as logging
import oslotest.base as oslotest
import requests
import webob
import webtest


class BaseTestCase(oslotest.BaseTestCase):
    def setUp(self):
        super(BaseTestCase, self).setUp()

        # If keystonemiddleware calls any deprecated function this will raise
        # an exception.
        warnings.filterwarnings('error', category=DeprecationWarning,
                                module='^keystonemiddleware\\.')
        self.addCleanup(warnings.resetwarnings)

        self.logger = self.useFixture(fixtures.FakeLogger(level=logging.DEBUG))


class TestCase(BaseTestCase):
    TEST_DOMAIN_ID = '1'
    TEST_DOMAIN_NAME = 'aDomain'
    TEST_GROUP_ID = uuid.uuid4().hex
    TEST_ROLE_ID = uuid.uuid4().hex
    TEST_TENANT_ID = '1'
    TEST_TENANT_NAME = 'aTenant'
    TEST_TOKEN = 'aToken'
    TEST_TRUST_ID = 'aTrust'
    TEST_USER = 'test'
    TEST_USER_ID = uuid.uuid4().hex

    TEST_ROOT_URL = 'http://127.0.0.1:5000/'

    def setUp(self):
        super(TestCase, self).setUp()
        self.time_patcher = mock.patch.object(time, 'time', lambda: 1234)
        self.time_patcher.start()

    def tearDown(self):
        self.time_patcher.stop()
        super(TestCase, self).tearDown()


if tuple(sys.version_info)[0:2] < (2, 7):

    def assertDictEqual(self, d1, d2, msg=None):
        # Simple version taken from 2.7
        self.assertIsInstance(d1, dict,
                              'First argument is not a dictionary')
        self.assertIsInstance(d2, dict,
                              'Second argument is not a dictionary')
        if d1 != d2:
            if msg:
                self.fail(msg)
            else:
                standardMsg = '%r != %r' % (d1, d2)
                self.fail(standardMsg)

    TestCase.assertDictEqual = assertDictEqual


class MiddlewareTestCase(BaseTestCase):

    def create_middleware(self, cb, **kwargs):
        raise NotImplemented("implement this in your tests")

    def create_simple_middleware(self,
                                 status='200 OK',
                                 body='',
                                 headers=None,
                                 **kwargs):
        def cb(req):
            resp = webob.Response(body, status)
            resp.headers.update(headers or {})
            return resp

        return self.create_middleware(cb, **kwargs)

    def create_app(self, *args, **kwargs):
        return webtest.TestApp(self.create_middleware(*args, **kwargs))

    def create_simple_app(self, *args, **kwargs):
        return webtest.TestApp(self.create_simple_middleware(*args, **kwargs))


class TestResponse(requests.Response):
    """Utility class to wrap requests.Response.

    Class used to wrap requests.Response and provide some convenience to
    initialize with a dict.
    """

    def __init__(self, data):
        self._text = None
        super(TestResponse, self).__init__()
        if isinstance(data, dict):
            self.status_code = data.get('status_code', 200)
            headers = data.get('headers')
            if headers:
                self.headers.update(headers)
            # Fake the text attribute to streamline Response creation
            # _content is defined by requests.Response
            self._content = data.get('text')
        else:
            self.status_code = data

    def __eq__(self, other):
        """Test if the response is equivalent to another response.

        This works by comparing the attribute dictionaries of both TestResponse
        instances.
        """
        return self.__dict__ == other.__dict__

    @property
    def text(self):
        return self.content


class DisableModuleFixture(fixtures.Fixture):
    """A fixture to provide support for unloading/disabling modules."""

    def __init__(self, module, *args, **kw):
        super(DisableModuleFixture, self).__init__(*args, **kw)
        self.module = module
        self._finders = []
        self._cleared_modules = {}

    def tearDown(self):
        super(DisableModuleFixture, self).tearDown()
        for finder in self._finders:
            sys.meta_path.remove(finder)
        sys.modules.update(self._cleared_modules)

    def clear_module(self):
        cleared_modules = {}
        for fullname in list(sys.modules.keys()):
            if (fullname == self.module or
                    fullname.startswith(self.module + '.')):
                cleared_modules[fullname] = sys.modules.pop(fullname)
        return cleared_modules

    def setUp(self):
        """Ensure ImportError for the specified module."""
        super(DisableModuleFixture, self).setUp()

        # Clear 'module' references in sys.modules
        self._cleared_modules.update(self.clear_module())

        finder = NoModuleFinder(self.module)
        self._finders.append(finder)
        sys.meta_path.insert(0, finder)


class NoModuleFinder(object):
    """Disallow further imports of 'module'."""

    def __init__(self, module):
        self.module = module

    def find_module(self, fullname, path):
        if fullname == self.module or fullname.startswith(self.module + '.'):
            raise ImportError
