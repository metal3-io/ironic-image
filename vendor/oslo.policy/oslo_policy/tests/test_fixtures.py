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

import json

from oslo_policy import fixture
from oslo_policy import policy as oslo_policy
from oslo_policy.tests import base as test_base


class FixtureTestCase(test_base.PolicyBaseTestCase):
    def test_enforce_http_true(self):
        self.assertTrue(self._test_enforce_http(True))

    def test_enforce_http_false(self):
        self.assertFalse(self._test_enforce_http(False))

    def _test_enforce_http(self, return_value):
        self.useFixture(fixture.HttpCheckFixture(return_value=return_value))
        action = self.getUniqueString()
        rules_json = {
            action: "http:" + self.getUniqueString()
        }
        rules = oslo_policy.Rules.load(json.dumps(rules_json))
        self.enforcer.set_rules(rules)
        return self.enforcer.enforce(rule=action,
                                     target={},
                                     creds={})

    def test_enforce_https_true(self):
        self.assertTrue(self._test_enforce_http(True))

    def test_enforce_https_false(self):
        self.assertFalse(self._test_enforce_http(False))

    def _test_enforce_https(self, return_value):
        self.useFixture(fixture.HttpsCheckFixture(return_value=return_value))
        action = self.getUniqueString()
        rules_json = {
            action: "https:" + self.getUniqueString()
        }
        rules = oslo_policy.Rules.load(json.dumps(rules_json))
        self.enforcer.set_rules(rules)
        return self.enforcer.enforce(rule=action,
                                     target={},
                                     creds={})
