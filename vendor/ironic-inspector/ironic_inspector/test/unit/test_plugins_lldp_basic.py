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

import mock

from ironic_inspector.common import lldp_parsers as nv
from ironic_inspector.plugins import lldp_basic
from ironic_inspector.test import base as test_base


class TestLLDPBasicProcessingHook(test_base.NodeTest):
    hook = lldp_basic.LLDPBasicProcessingHook()

    def setUp(self):
        super(TestLLDPBasicProcessingHook, self).setUp()
        self.data = {
            'inventory': {
                'interfaces': [{
                    'name': 'em1',
                }],
                'cpu': 1,
                'disks': 1,
                'memory': 1
            },
            'all_interfaces':
            {
                'em1': {'mac': self.macs[0], 'ip': self.ips[0]}
            }
        }

        self.expected = {"em1": {"ip": self.ips[0], "mac": self.macs[0]}}

    def test_all_valid_data(self):

        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [1, "04112233aabbcc"],  # ChassisId
                [2, "07373334"],        # PortId
                [3, "003c"],            # TTL
                [4, "686f737430322e6c61622e656e6720706f7274203320"
                 "28426f6e6429"],  # PortDesc
                [5, "737730312d646973742d31622d623132"],  # SysName
                [6, "4e6574776f726b732c20496e632e20353530302c2076657273696f"
                 "6e203132204275696c6420646174653a20323031342d30332d31332030"
                 "383a33383a33302055544320"],  # SysDesc
                [7, "00140014"],  # SysCapabilities
                [8, "0501c000020f020000000000"],  # MgmtAddress
                [8, "110220010db885a3000000008a2e03707334020000000000"],
                [8, "0706aa11bb22cc3302000003e900"],  # MgmtAddress
                [127, "00120f01036c110010"],  # dot3 MacPhyConfigStatus
                [127, "00120f030300000002"],  # dot3 LinkAggregation
                [127, "00120f0405ea"],  # dot3 MTU
                [127, "0080c2010066"],  # dot1 PortVlan
                [127, "0080c20206000a"],  # dot1 PortProtocolVlanId
                [127, "0080c202060014"],  # dot1 PortProtocolVlanId
                [127, "0080c204080026424203000000"],   # dot1 ProtocolIdentity
                [127, "0080c203006507766c616e313031"],  # dot1 VlanName
                [127, "0080c203006607766c616e313032"],  # dot1 VlanName
                [127, "0080c203006807766c616e313034"],  # dot1 VlanName
                [127, "0080c2060058"],  # dot1 MgmtVID
                [0, ""]]
            }]

        expected = {
            nv.LLDP_CAP_ENABLED_NM: ['Bridge', 'Router'],
            nv.LLDP_CAP_SUPPORT_NM: ['Bridge', 'Router'],
            nv.LLDP_CHASSIS_ID_NM: "11:22:33:aa:bb:cc",
            nv.LLDP_MGMT_ADDRESSES_NM: ['192.0.2.15',
                                        '2001:db8:85a3::8a2e:370:7334',
                                        'aa:11:bb:22:cc:33'],
            nv.LLDP_PORT_LINK_AUTONEG_ENABLED_NM: True,
            nv.LLDP_PORT_LINK_AUTONEG_ENABLED_NM: True,
            nv.LLDP_PORT_DESC_NM: 'host02.lab.eng port 3 (Bond)',
            nv.LLDP_PORT_ID_NM: '734',
            nv.LLDP_PORT_LINK_AGG_ENABLED_NM: True,
            nv.LLDP_PORT_LINK_AGG_ID_NM: 2,
            nv.LLDP_PORT_LINK_AGG_SUPPORT_NM: True,
            nv.LLDP_PORT_MGMT_VLANID_NM: 88,
            nv.LLDP_PORT_MAU_TYPE_NM: '100BASE-TX full duplex',
            nv.LLDP_MTU_NM: 1514,
            nv.LLDP_PORT_CAPABILITIES_NM: ['1000BASE-T fdx',
                                           '100BASE-TX fdx',
                                           '100BASE-TX hdx',
                                           '10BASE-T fdx',
                                           '10BASE-T hdx',
                                           'Asym and Sym PAUSE fdx'],
            nv.LLDP_PORT_PROT_VLAN_ENABLED_NM: True,
            nv.LLDP_PORT_PROT_VLANIDS_NM: [10, 20],
            nv.LLDP_PORT_PROT_VLAN_SUPPORT_NM: True,
            nv.LLDP_PORT_VLANID_NM: 102,
            nv.LLDP_PORT_VLANS_NM: [{'id': 101, 'name': 'vlan101'},
                                    {'id': 102, 'name': 'vlan102'},
                                    {'id': 104, "name": 'vlan104'}],
            nv.LLDP_PROTOCOL_IDENTITIES_NM: ['0026424203000000'],
            nv.LLDP_SYS_DESC_NM: 'Networks, Inc. 5500, version 12'
            ' Build date: 2014-03-13 08:38:30 UTC ',
            nv.LLDP_SYS_NAME_NM: 'sw01-dist-1b-b12'
        }

        self.hook.before_update(self.data, self.node_info)

        actual_all_int = self.data['all_interfaces']
        actual = actual_all_int['em1']['lldp_processed']

        for name, value in expected.items():
            if name is nv.LLDP_PORT_VLANS_NM:
                for d1, d2 in zip(expected[name], actual[name]):
                    for key, value in d1.items():
                        self.assertEqual(d2[key], value)
            else:
                self.assertEqual(actual[name], expected[name])

    def test_multiple_interfaces(self):
        self.data = {
            'inventory': {
                'interfaces': [
                    {'name': 'em1',
                     'lldp': [
                         [1, "04112233aabbcc"],
                         [2, "07373334"],
                         [3, "003c"]]},
                    {'name': 'em2',
                     'lldp': [
                         [1, "04112233aabbdd"],
                         [2, "07373838"],
                         [3, "003c"]]},
                    {'name': 'em3',
                     'lldp': [
                         [1, "04112233aabbee"],
                         [2, "07373939"],
                         [3, "003c"]]}],
                'cpu': 1,
                'disks': 1,
                'memory': 1
                },
            'all_interfaces':
            {
                'em1': {'mac': self.macs[0], 'ip': self.ips[0]},
                'em2': {'mac': self.macs[0], 'ip': self.ips[0]},
                'em3': {'mac': self.macs[0], 'ip': self.ips[0]}
            }
        }

        expected = {"em1": {"ip": self.ips[0], "mac": self.macs[0],
                            "lldp_processed": {
                                nv.LLDP_CHASSIS_ID_NM: "11:22:33:aa:bb:cc",
                                nv.LLDP_PORT_ID_NM: "734"}},
                    "em2": {"ip": self.ips[0], "mac": self.macs[0],
                            "lldp_processed": {
                                nv.LLDP_CHASSIS_ID_NM: "11:22:33:aa:bb:dd",
                                nv.LLDP_PORT_ID_NM: "788"}},
                    "em3": {"ip": self.ips[0], "mac": self.macs[0],
                            "lldp_processed": {
                                nv.LLDP_CHASSIS_ID_NM: "11:22:33:aa:bb:ee",
                                nv.LLDP_PORT_ID_NM: "799"}}}

        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(expected, self.data['all_interfaces'])

    def test_chassis_ids(self):
        # Test IPv4 address
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [1, "0501c000020f"],
                ]}]

        self.expected['em1']['lldp_processed'] = {
            nv.LLDP_CHASSIS_ID_NM: "192.0.2.15"
            }
        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])

        # Test name
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [1, "0773773031"],
            ]}]

        self.expected['em1']['lldp_processed'] = {
            nv.LLDP_CHASSIS_ID_NM: "sw01"
        }
        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])

    def test_duplicate_tlvs(self):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [1, "04112233aabbcc"],  # ChassisId
                [1, "04332211ddeeff"],  # ChassisId
                [1, "04556677aabbcc"],  # ChassisId
                [2, "07373334"],  # PortId
                [2, "07373435"],  # PortId
                [2, "07373536"]   # PortId
                ]}]

        # Only the first unique TLV is processed
        self.expected['em1']['lldp_processed'] = {
            nv.LLDP_CHASSIS_ID_NM: "11:22:33:aa:bb:cc",
            nv.LLDP_PORT_ID_NM: "734"
            }

        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])

    def test_unhandled_tlvs(self):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [10, "04112233aabbcc"],
                [12, "07373334"],
                [128, "00120f080300010000"]]}]

        # nothing should be written to lldp_processed
        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])

    def test_unhandled_oui(self):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [127, "00906901425030323134323530393236"],
                [127, "23ac0074657374"],
                [127, "00120e010300010000"]]}]

        # nothing should be written to lldp_processed
        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])

    @mock.patch('ironic_inspector.common.lldp_parsers.LOG')
    def test_null_strings(self, mock_log):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [1, "04"],
                [4, ""],  # PortDesc
                [5, ""],  # SysName
                [6, ""],  # SysDesc
                [127, "0080c203006507"]  # dot1 VlanName
            ]}]

        self.expected['em1']['lldp_processed'] = {
            nv.LLDP_PORT_DESC_NM: '',
            nv.LLDP_SYS_DESC_NM: '',
            nv.LLDP_SYS_NAME_NM: ''
        }

        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])
        self.assertEqual(2, mock_log.warning.call_count)

    @mock.patch('ironic_inspector.common.lldp_parsers.LOG')
    def test_truncated_int(self, mock_log):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [127, "00120f04"],  # dot3 MTU
                [127, "0080c201"],  # dot1 PortVlan
                [127, "0080c206"],  # dot1 MgmtVID
                ]}]

        # nothing should be written to lldp_processed
        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])
        self.assertEqual(3, mock_log.warning.call_count)

    @mock.patch('ironic_inspector.common.lldp_parsers.LOG')
    def test_invalid_ip(self, mock_log):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [8, "0501"],  # truncated
                [8, "0507c000020f020000000000"]]  # invalid id
        }]
        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])
        self.assertEqual(2, mock_log.warning.call_count)

    @mock.patch('ironic_inspector.common.lldp_parsers.LOG')
    def test_truncated_mac(self, mock_log):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [8, "0506"]]
        }]

        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])
        self.assertEqual(1, mock_log.warning.call_count)

    @mock.patch('ironic_inspector.common.lldp_parsers.LOG')
    def test_bad_value_macphy(self, mock_log):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [127, "00120f01036c11FFFF"],  # invalid mau type
                [127, "00120f01036c11"],      # truncated
                [127, "00120f01036c"]         # truncated
            ]}]

        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])
        self.assertEqual(3, mock_log.warning.call_count)

    @mock.patch('ironic_inspector.common.lldp_parsers.LOG')
    def test_bad_value_linkagg(self, mock_log):
        self.data['inventory']['interfaces'] = [{
            'name': 'em1',
            'lldp': [
                [127, "00120f0303"],  # dot3 LinkAggregation
                [127, "00120f03"]     # truncated
                ]}]

        self.hook.before_update(self.data, self.node_info)
        self.assertEqual(self.expected, self.data['all_interfaces'])
        self.assertEqual(2, mock_log.warning.call_count)
