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

"""Generic LLDP Processing Hook"""

import binascii

from construct import core
from ironicclient import exceptions
import netaddr
from oslo_config import cfg
from oslo_utils import netutils

from ironic_inspector.common import lldp_parsers
from ironic_inspector.common import lldp_tlvs as tlv
from ironic_inspector.plugins import base
from ironic_inspector import utils

LOG = utils.getProcessingLogger(__name__)

CONF = cfg.CONF

PORT_ID_ITEM_NAME = "port_id"
SWITCH_ID_ITEM_NAME = "switch_id"

LLDP_PROC_DATA_MAPPING =\
    {lldp_parsers.LLDP_CHASSIS_ID_NM: SWITCH_ID_ITEM_NAME,
     lldp_parsers.LLDP_PORT_ID_NM: PORT_ID_ITEM_NAME}


class GenericLocalLinkConnectionHook(base.ProcessingHook):
    """Process mandatory LLDP packet fields

    Non-vendor specific LLDP packet fields processed for each NIC found for a
    baremetal node, port ID and chassis ID. These fields if found and if valid
    will be saved into the local link connection info port id and switch id
    fields on the Ironic port that represents that NIC.
    """

    def _get_local_link_patch(self, tlv_type, tlv_value, port, node_info):
        try:
            data = bytearray(binascii.unhexlify(tlv_value))
        except TypeError:
            LOG.warning("TLV value for TLV type %d not in correct"
                        "format, ensure TLV value is in "
                        "hexidecimal format when sent to "
                        "inspector", tlv_type, node_info=node_info)
            return

        item = value = None
        if tlv_type == tlv.LLDP_TLV_PORT_ID:
            try:
                port_id = tlv.PortId.parse(data)
            except (core.MappingError, netaddr.AddrFormatError) as e:
                LOG.warning("TLV parse error for Port ID: %s", e,
                            node_info=node_info)
                return

            item = PORT_ID_ITEM_NAME
            value = port_id.value
        elif tlv_type == tlv.LLDP_TLV_CHASSIS_ID:
            try:
                chassis_id = tlv.ChassisId.parse(data)
            except (core.MappingError, netaddr.AddrFormatError) as e:
                LOG.warning("TLV parse error for Chassis ID: %s", e,
                            node_info=node_info)
                return

            # Only accept mac address for chassis ID
            if 'mac_address' in chassis_id.subtype:
                item = SWITCH_ID_ITEM_NAME
                value = chassis_id.value

        if item and value:
            if (not CONF.processing.overwrite_existing and
                    item in port.local_link_connection):
                return
            return {'op': 'add',
                    'path': '/local_link_connection/%s' % item,
                    'value': value}

    def _get_lldp_processed_patch(self, name, item, lldp_proc_data, port,
                                  node_info):

        if 'lldp_processed' not in lldp_proc_data:
            return

        value = lldp_proc_data['lldp_processed'].get(name)

        if value:

            # Only accept mac address for chassis ID
            if (item == SWITCH_ID_ITEM_NAME and
                    not netutils.is_valid_mac(value)):
                LOG.info("Skipping switch_id since it's not a MAC: %s", value,
                         node_info=node_info)
                return

            if (not CONF.processing.overwrite_existing and
                    item in port.local_link_connection):
                return
            return {'op': 'add',
                    'path': '/local_link_connection/%s' % item,
                    'value': value}

    def before_update(self, introspection_data, node_info, **kwargs):
        """Process LLDP data and patch Ironic port local link connection"""
        inventory = utils.get_inventory(introspection_data)

        ironic_ports = node_info.ports()

        for iface in inventory['interfaces']:
            if iface['name'] not in introspection_data['all_interfaces']:
                continue

            mac_address = iface['mac_address']
            port = ironic_ports.get(mac_address)
            if not port:
                LOG.debug("Skipping LLC processing for interface %s, matching "
                          "port not found in Ironic.", mac_address,
                          node_info=node_info, data=introspection_data)
                continue

            lldp_data = iface.get('lldp')
            if lldp_data is None:
                LOG.warning("No LLDP Data found for interface %s",
                            mac_address, node_info=node_info,
                            data=introspection_data)
                continue

            patches = []
            # First check if lldp data was already processed by lldp_basic
            # plugin which stores data in 'all_interfaces'
            proc_data = introspection_data['all_interfaces'][iface['name']]

            for name, item in LLDP_PROC_DATA_MAPPING.items():
                patch = self._get_lldp_processed_patch(name, item,
                                                       proc_data, port,
                                                       node_info)
                if patch is not None:
                    patches.append(patch)

            # If no processed lldp data was available then parse raw lldp data
            if not patches:
                for tlv_type, tlv_value in lldp_data:
                    patch = self._get_local_link_patch(tlv_type, tlv_value,
                                                       port, node_info)
                    if patch is not None:
                        patches.append(patch)

            try:
                node_info.patch_port(port, patches)
            except exceptions.BadRequest as e:
                LOG.warning("Failed to update port %(uuid)s: %(error)s",
                            {'uuid': port.uuid, 'error': e},
                            node_info=node_info)
