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

"""Gather capabilities from inventory."""

from oslo_config import cfg

from ironic_inspector.plugins import base
from ironic_inspector import utils


CONF = cfg.CONF
LOG = utils.getProcessingLogger(__name__)


class CapabilitiesHook(base.ProcessingHook):
    """Processing hook for detecting capabilities."""

    def _detect_boot_mode(self, inventory, node_info, data=None):
        boot_mode = inventory.get('boot', {}).get('current_boot_mode')
        if boot_mode is not None:
            LOG.info('Boot mode was %s', boot_mode,
                     data=data, node_info=node_info)
            return {'boot_mode': boot_mode}
        else:
            LOG.warning('No boot mode information available',
                        data=data, node_info=node_info)
            return {}

    def _detect_cpu_flags(self, inventory, node_info, data=None):
        flags = inventory['cpu'].get('flags')
        if not flags:
            LOG.warning('No CPU flags available, please update your '
                        'introspection ramdisk',
                        data=data, node_info=node_info)
            return {}

        flags = set(flags)
        caps = {}
        for flag, name in CONF.capabilities.cpu_flags.items():
            if flag in flags:
                caps[name] = 'true'

        LOG.info('CPU capabilities: %s', list(caps),
                 data=data, node_info=node_info)
        return caps

    def before_update(self, introspection_data, node_info, **kwargs):
        inventory = utils.get_inventory(introspection_data)
        caps = {}
        if CONF.capabilities.boot_mode:
            caps.update(self._detect_boot_mode(inventory, node_info,
                                               introspection_data))

        caps.update(self._detect_cpu_flags(inventory, node_info,
                                           introspection_data))

        if caps:
            LOG.debug('New capabilities: %s', caps, node_info=node_info,
                      data=introspection_data)
            node_info.update_capabilities(**caps)
        else:
            LOG.debug('No new capabilities detected', node_info=node_info,
                      data=introspection_data)
