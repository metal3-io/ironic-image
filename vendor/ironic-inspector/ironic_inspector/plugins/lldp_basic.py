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

"""LLDP Processing Hook for basic TLVs"""

import binascii

from ironic_inspector.common import lldp_parsers
from ironic_inspector.plugins import base
from ironic_inspector import utils

LOG = utils.getProcessingLogger(__name__)


class LLDPBasicProcessingHook(base.ProcessingHook):
    """Process mandatory and optional LLDP packet fields

       Loop through raw LLDP TLVs and parse those from the
       basic management, 802.1, and 802.3 TLV sets.
       Store parsed data back to the ironic-inspector database.
    """

    def _parse_lldp_tlvs(self, tlvs, node_info):
        """Parse LLDP TLVs into dictionary of name/value pairs

        :param tlvs: list of raw TLVs
        :param node_info: node being introspected
        :returns nv: dictionary of name/value pairs. The
                     LLDP user-friendly names, e.g.
                     "switch_port_id" are the keys
        """

        # Generate name/value pairs for each TLV supported by this plugin.
        parser = lldp_parsers.LLDPBasicMgmtParser(node_info)

        for tlv_type, tlv_value in tlvs:
            try:
                data = bytearray(binascii.a2b_hex(tlv_value))
            except TypeError as e:
                LOG.warning(
                    "TLV value for TLV type %(tlv_type)d not in correct "
                    "format, value must be in hexadecimal: %(msg)s",
                    {'tlv_type': tlv_type, 'msg': e},  node_info=node_info)
                continue

            if parser.parse_tlv(tlv_type, data):
                LOG.debug("Handled TLV type %d",
                          tlv_type, node_info=node_info)
            else:
                LOG.debug("LLDP TLV type %d not handled",
                          tlv_type, node_info=node_info)

        return parser.nv_dict

    def before_update(self, introspection_data, node_info, **kwargs):
        """Process LLDP data and update all_interfaces with processed data"""

        inventory = utils.get_inventory(introspection_data)

        for iface in inventory['interfaces']:
            if_name = iface['name']

            tlvs = iface.get('lldp')
            if tlvs is None:
                LOG.warning("No LLDP Data found for interface %s",
                            if_name, node_info=node_info)
                continue

            LOG.debug("Processing LLDP Data for interface %s",
                      if_name, node_info=node_info)

            nv = self._parse_lldp_tlvs(tlvs, node_info)

            if nv:
                # Store lldp data per interface in "all_interfaces"
                iface_to_update = introspection_data['all_interfaces'][if_name]
                iface_to_update['lldp_processed'] = nv
