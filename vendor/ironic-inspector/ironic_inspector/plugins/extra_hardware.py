# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Plugin to store extra hardware information in Swift.

Stores the value of the 'data' key returned by the ramdisk as a JSON encoded
string in a Swift object. The object is named 'extra_hardware-<node uuid>' and
is stored in the 'inspector' container.
"""

import json

from ironic_inspector.common import swift
from ironic_inspector.plugins import base
from ironic_inspector import utils

LOG = utils.getProcessingLogger(__name__)
EDEPLOY_ITEM_SIZE = 4


class ExtraHardwareHook(base.ProcessingHook):
    """Processing hook for saving extra hardware information in Swift."""

    def _store_extra_hardware(self, name, data):
        """Handles storing the extra hardware data from the ramdisk"""
        swift_api = swift.SwiftAPI()
        swift_api.create_object(name, data)

    def before_update(self, introspection_data, node_info, **kwargs):
        """Stores the 'data' key from introspection_data in Swift.

        If the 'data' key exists, updates Ironic extra column
        'hardware_swift_object' key to the name of the Swift object, and stores
        the data in the 'inspector' container in Swift.

        Otherwise, it does nothing.
        """
        if 'data' not in introspection_data:
            LOG.warning('No extra hardware information was received from '
                        'the ramdisk', node_info=node_info,
                        data=introspection_data)
            return
        data = introspection_data['data']

        name = 'extra_hardware-%s' % node_info.uuid
        try:
            self._store_extra_hardware(name, json.dumps(data))
        except utils.Error as e:
            LOG.error("Failed to save extra hardware information in "
                      "Swift: %s", e, node_info=node_info)
        else:
            node_info.patch([{'op': 'add',
                              'path': '/extra/hardware_swift_object',
                              'value': name}])

        # NOTE(sambetts) If data is edeploy format, convert to dicts for rules
        # processing, store converted data in introspection_data['extra'].
        # Delete introspection_data['data'], it is assumed unusable
        # by rules.
        if self._is_edeploy_data(data):
            LOG.debug('Extra hardware data is in eDeploy format, '
                      'converting to usable format',
                      node_info=node_info, data=introspection_data)
            introspection_data['extra'] = self._convert_edeploy_data(data)
        else:
            LOG.warning('Extra hardware data was not in a recognised '
                        'format (eDeploy), and will not be forwarded to '
                        'introspection rules', node_info=node_info,
                        data=introspection_data)

        LOG.debug('Deleting \"data\" key from introspection data as it is '
                  'assumed unusable by introspection rules. Raw data is '
                  'stored in swift',
                  node_info=node_info, data=introspection_data)
        del introspection_data['data']

    def _is_edeploy_data(self, data):
        return all(isinstance(item, list) and len(item) == EDEPLOY_ITEM_SIZE
                   for item in data)

    def _convert_edeploy_data(self, data):
        converted = {}
        for item in data:
            converted_0 = converted.setdefault(item[0], {})
            converted_1 = converted_0.setdefault(item[1], {})

            try:
                item[3] = int(item[3])
            except (ValueError, TypeError):
                pass

            converted_1[item[2]] = item[3]
        return converted
