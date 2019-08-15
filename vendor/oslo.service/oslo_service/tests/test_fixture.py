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

from oslo_service import fixture
from oslo_service import loopingcall


class FixtureTestCase(test_base.BaseTestCase):
    def setUp(self):
        super(FixtureTestCase, self).setUp()
        self.sleepfx = self.useFixture(fixture.SleepFixture())

    def test_sleep_fixture(self):
        @loopingcall.RetryDecorator(max_retry_count=3, inc_sleep_time=2,
                                    exceptions=(ValueError,))
        def retried_method():
            raise ValueError("!")

        self.assertRaises(ValueError, retried_method)
        self.assertEqual(3, self.sleepfx.mock_wait.call_count)
        # TODO(efried): This is cheating, and shouldn't be done by real callers
        # yet - see todo in SleepFixture.
        self.sleepfx.mock_wait.assert_has_calls(
            [mock.call(x) for x in (2, 4, 6)])
