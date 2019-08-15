# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslotest import base
import stevedore
from testtools import matchers


class TestPasteDeploymentEntryPoints(base.BaseTestCase):

    def test_entry_points(self):
        factory_classes = {
            'catch_errors': 'CatchErrors',
            'correlation_id': 'CorrelationId',
            'cors': 'CORS',
            'debug': 'Debug',
            'healthcheck': 'Healthcheck',
            'http_proxy_to_wsgi': 'HTTPProxyToWSGI',
            'request_id': 'RequestId',
            'sizelimit': 'RequestBodySizeLimiter',
            'ssl': 'SSLMiddleware',
        }

        em = stevedore.ExtensionManager('paste.filter_factory')

        # Ensure all the factories are defined by their names
        factory_names = [extension.name for extension in em]
        self.assertThat(factory_names,
                        matchers.ContainsAll(factory_classes))
