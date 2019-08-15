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

import stevedore
from testtools import matchers

from keystonemiddleware.tests.unit import utils


class TestPasteDeploymentEntryPoints(utils.BaseTestCase):

    def test_entry_points(self):
        expected_factory_names = [
            'audit',
            'auth_token',
            'ec2_token',
            's3_token',
        ]
        em = stevedore.ExtensionManager('paste.filter_factory')

        exp_factories = set(['keystonemiddleware.' + name + ':filter_factory'
                             for name in expected_factory_names])
        actual_factories = set(['{0.__module__}:{0.__name__}'.format(
            extension.plugin) for extension in em])
        # Ensure that all factories are defined by their names
        self.assertThat(actual_factories, matchers.ContainsAll(exp_factories))
