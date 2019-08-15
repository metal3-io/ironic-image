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

from oslo_config import cfg


HEALTHCHECK_OPTS = [
    cfg.StrOpt('path',
               default='/healthcheck',
               deprecated_for_removal=True,
               help='The path to respond to healtcheck requests on.'),
    cfg.BoolOpt('detailed',
                default=False,
                help='Show more detailed information as part of the response. '
                     'Security note: Enabling this option may expose '
                     'sensitive details about the service being monitored. '
                     'Be sure to verify that it will not violate your '
                     'security policies.'),
    cfg.ListOpt('backends',
                default=[],
                help='Additional backends that can perform health checks and '
                     'report that information back as part of a request.'),
]


DISABLE_BY_FILE_OPTS = [
    cfg.StrOpt('disable_by_file_path',
               default=None,
               help='Check the presence of a file to determine if an '
                    'application is running on a port. Used by '
                    'DisableByFileHealthcheck plugin.'),
]


DISABLE_BY_FILES_OPTS = [
    cfg.ListOpt('disable_by_file_paths',
                default=[],
                help='Check the presence of a file based on a port to '
                     'determine if an application is running on a port. '
                     'Expects a "port:path" list of strings. Used by '
                     'DisableByFilesPortsHealthcheck plugin.'),
]
