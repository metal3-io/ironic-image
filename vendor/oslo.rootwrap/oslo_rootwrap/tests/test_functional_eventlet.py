# Copyright (c) 2014 Mirantis Inc.
# All Rights Reserved.
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

import os

if os.environ.get('TEST_EVENTLET', False):
    import eventlet
    eventlet.monkey_patch()

    from oslo_rootwrap.tests import test_functional

    class RootwrapDaemonTest(test_functional.RootwrapDaemonTest):
        def assert_unpatched(self):
            # This test case is specifically for eventlet testing
            pass

        def _thread_worker(self, seconds, msg):
            code, out, err = self.execute(
                ['sh', '-c', 'sleep %d; echo %s' % (seconds, msg)])
            # Ignore trailing newline
            self.assertEqual(msg, out.rstrip())

        def _thread_worker_timeout(self, seconds, msg, timeout):
            with eventlet.Timeout(timeout):
                try:
                    self._thread_worker(seconds, msg)
                except eventlet.Timeout:
                    pass

        def test_eventlet_threads(self):
            """Check eventlet compatibility.

            The multiprocessing module is not eventlet friendly and
            must be protected against eventlet thread switching and its
            timeout exceptions.
            """
            th = []
            # 10 was not enough for some reason.
            for i in range(15):
                th.append(
                    eventlet.spawn(self._thread_worker, i % 3, 'abc%d' % i))
            for i in [5, 17, 20, 25]:
                th.append(
                    eventlet.spawn(self._thread_worker_timeout, 2,
                                   'timeout%d' % i, i))
            for thread in th:
                thread.wait()
