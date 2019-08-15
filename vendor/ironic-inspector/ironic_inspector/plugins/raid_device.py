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

"""Gather root device hint from recognized block devices."""

from ironic_inspector.plugins import base
from ironic_inspector import utils


LOG = utils.getProcessingLogger(__name__)


class RaidDeviceDetection(base.ProcessingHook):
    """Processing hook for learning the root device after RAID creation.

    The plugin can figure out the root device in 2 runs. First, it saves the
    discovered block device serials in node.extra. The second run will check
    the difference between the recently discovered block devices and the
    previously saved ones. After saving the root device in node.properties, it
    will delete the temporarily saved block device serials in node.extra.

    This way, it helps to figure out the root device hint in cases when
    otherwise Ironic doesn't have enough information to do so. Such a usecase
    is DRAC RAID configuration where the BMC doesn't provide any useful
    information about the created RAID disks. Using this plugin immediately
    before and after creating the root RAID device will solve the issue of root
    device hints.

    In cases where there's no RAID volume on the node, the standard plugin will
    fail due to the missing local_gb value. This plugin fakes the missing
    value, until it's corrected during later runs. Note, that for this to work
    the plugin needs to take precedence over the standard plugin.
    """

    def _get_serials(self, data):
        if 'inventory' in data:
            return [x['serial'] for x in data['inventory'].get('disks', ())
                    if x.get('serial')]
        elif 'block_devices' in data:
            return data['block_devices'].get('serials', ())

    def before_processing(self, introspection_data, **kwargs):
        """Adds fake local_gb value if it's missing from introspection_data."""
        if not introspection_data.get('local_gb'):
            LOG.info('No volume is found on the node. Adding a fake '
                     'value for "local_gb"', data=introspection_data)
            introspection_data['local_gb'] = 1

    def before_update(self, introspection_data, node_info, **kwargs):
        current_devices = self._get_serials(introspection_data)
        if not current_devices:
            LOG.warning('No block device was received from ramdisk',
                        node_info=node_info, data=introspection_data)
            return

        node = node_info.node()

        if 'root_device' in node.properties:
            LOG.info('Root device is already known for the node',
                     node_info=node_info, data=introspection_data)
            return

        if 'block_devices' in node.extra:
            # Compare previously discovered devices with the current ones
            previous_devices = node.extra['block_devices']['serials']
            new_devices = [device for device in current_devices
                           if device not in previous_devices]

            if len(new_devices) > 1:
                LOG.warning('Root device cannot be identified because '
                            'multiple new devices were found',
                            node_info=node_info, data=introspection_data)
                return
            elif len(new_devices) == 0:
                LOG.warning('No new devices were found',
                            node_info=node_info, data=introspection_data)
                return

            node_info.patch([
                {'op': 'remove',
                 'path': '/extra/block_devices'},
                {'op': 'add',
                 'path': '/properties/root_device',
                 'value': {'serial': new_devices[0]}}
            ])

        else:
            # No previously discovered devices - save the inspector block
            # devices in node.extra
            node_info.patch([{'op': 'add',
                              'path': '/extra/block_devices',
                              'value': {'serials': current_devices}}])
