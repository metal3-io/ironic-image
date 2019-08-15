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

import fixtures


class SleepFixture(fixtures.Fixture):
    """A fixture for mocking the ``wait()`` within :doc:`loopingcall` events.

    This exists so test cases can exercise code that uses :doc:`loopingcall`
    without actually incurring wall clock time for sleeping.

    The mock for the ``wait()`` is accessible via the fixture's ``mock_wait``
    attribute.

    .. note:: It is not recommended to assert specific arguments (i.e. timeout
              values) to the mock, as this relies on the internals of
              :doc:`loopingcall` not changing.

    .. todo:: Figure out a way to make an enforceable contract allowing
              verification of timeout values.

    Example usage::

        from oslo.service import fixture
        ...
        class MyTest(...):
            def setUp(self):
                ...
                self.sleepfx = self.useFixture(fixture.SleepFixture())
                ...

            def test_this(self):
                ...
                thing_that_hits_a_loopingcall()
                ...
                self.assertEqual(5, self.sleepfx.mock_wait.call_count)
                ...
    """
    def _setUp(self):
        # Provide access to the mock so that calls to it can be asserted
        self.mock_wait = self.useFixture(fixtures.MockPatch(
            'oslo_utils.eventletutils.EventletEvent.wait')).mock
