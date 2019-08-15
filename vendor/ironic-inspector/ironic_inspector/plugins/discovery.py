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

"""Enroll node not found hook hook."""

from oslo_config import cfg

from ironic_inspector.common import ironic as ir_utils
from ironic_inspector import node_cache
from ironic_inspector import utils


CONF = cfg.CONF

LOG = utils.getProcessingLogger(__name__)


def _extract_node_driver_info(introspection_data):
    node_driver_info = {}
    for ip_version in CONF.discovery.enabled_bmc_address_version:
        address = None
        if ip_version == '4':
            address = utils.get_ipmi_address_from_data(introspection_data)
        elif ip_version == '6':
            address = utils.get_ipmi_v6address_from_data(introspection_data)

        if address:
            node_driver_info['ipmi_address'] = address
            break
    else:
        LOG.warning('No BMC address provided, discovered node will be '
                    'created without ipmi address')
    return node_driver_info


def _check_existing_nodes(introspection_data, node_driver_info, ironic):
    macs = utils.get_valid_macs(introspection_data)
    if macs:
        ir_utils.lookup_node_by_macs(macs, introspection_data, ironic=ironic,
                                     fail=True)
    else:
        LOG.warning('No suitable interfaces found for discovered node. '
                    'Check that validate_interfaces hook is listed in '
                    '[processing]default_processing_hooks config option')

    # verify existing node with discovered ipmi address
    ipmi_address = node_driver_info.get('ipmi_address')
    if ipmi_address:
        ir_utils.lookup_node_by_bmc_addresses([ipmi_address],
                                              introspection_data,
                                              ironic=ironic, fail=True)


def enroll_node_not_found_hook(introspection_data, **kwargs):
    node_attr = {}
    ironic = ir_utils.get_client()

    node_driver_info = _extract_node_driver_info(introspection_data)
    node_attr['driver_info'] = node_driver_info

    node_driver = CONF.discovery.enroll_node_driver

    _check_existing_nodes(introspection_data, node_driver_info, ironic)
    LOG.debug('Creating discovered node with driver %(driver)s and '
              'attributes: %(attr)s',
              {'driver': node_driver, 'attr': node_attr},
              data=introspection_data)
    # NOTE(aarefiev): This flag allows to distinguish enrolled manually
    # and auto-discovered nodes in the introspection rules.
    introspection_data['auto_discovered'] = True
    return node_cache.create_node(node_driver, ironic=ironic, **node_attr)
