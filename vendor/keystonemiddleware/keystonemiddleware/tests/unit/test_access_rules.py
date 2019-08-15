# Copyright 2019 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from keystonemiddleware.auth_token import _path_matches
from keystonemiddleware.tests.unit import utils


class TestAccessRules(utils.BaseTestCase):

    def test_path_matches(self):
        good_matches = [
            ('/v2/servers', '/v2/servers'),
            ('/v2/servers/123', '/v2/servers/{server_id}'),
            ('/v2/servers/123/', '/v2/servers/{server_id}/'),
            ('/v2/servers/123', '/v2/servers/*'),
            ('/v2/servers/123/', '/v2/servers/*/'),
            ('/v2/servers/123', '/v2/servers/**'),
            ('/v2/servers/123/', '/v2/servers/**'),
            ('/v2/servers/123/456', '/v2/servers/**'),
            ('/v2/servers', '**'),
            ('/v2/servers/', '**'),
            ('/v2/servers/123', '**'),
            ('/v2/servers/123/456', '**'),
            ('/v2/servers/123/volume/456', '**'),
            ('/v2/servers/123/456', '/v2/*/*/*'),
            ('/v2/123/servers/466', '/v2/{project_id}/servers/{server_id}'),
        ]
        for (request, pattern) in good_matches:
            self.assertIsNotNone(_path_matches(request, pattern))
        bad_matches = [
            ('/v2/servers/someuuid', '/v2/servers'),
            ('/v2/servers//', '/v2/servers/{server_id}'),
            ('/v2/servers/123/', '/v2/servers/{server_id}'),
            ('/v2/servers/123/456', '/v2/servers/{server_id}'),
            ('/v2/servers/123/456', '/v2/servers/*'),
            ('/v2/servers', 'v2/servers'),
            ('/v2/servers/123/456/789', '/v2/*/*/*'),
            ('/v2/servers/123/', '/v2/*/*/*'),
            ('/v2/servers/', '/v2/servers/{server_id}'),
            ('/v2/servers', '/v2/servers/{server_id}'),
        ]
        for (request, pattern) in bad_matches:
            self.assertIsNone(_path_matches(request, pattern))
