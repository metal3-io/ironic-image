# Copyright (c) 2013 Rackspace Hosting
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

import fixtures
import mock
from oslotest import base as test_base

from oslo_middleware import correlation_id


class CorrelationIdTest(test_base.BaseTestCase):

    def setUp(self):
        super(CorrelationIdTest, self).setUp()

    def test_process_request(self):
        app = mock.Mock()
        req = mock.Mock()
        req.headers = {}

        mock_uuid4 = mock.Mock()
        mock_uuid4.return_value = "fake_uuid"
        self.useFixture(fixtures.MockPatch('uuid.uuid4', mock_uuid4))

        middleware = correlation_id.CorrelationId(app)
        middleware(req)

        self.assertEqual("fake_uuid", req.headers.get("X_CORRELATION_ID"))

    def test_process_request_should_not_regenerate_correlation_id(self):
        app = mock.Mock()
        req = mock.Mock()
        req.headers = {"X_CORRELATION_ID": "correlation_id"}

        middleware = correlation_id.CorrelationId(app)
        middleware(req)

        self.assertEqual("correlation_id", req.headers.get("X_CORRELATION_ID"))
