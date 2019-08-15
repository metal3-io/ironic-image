# -*- coding: utf-8 -*-

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

TRAITS = [
    'TSO',  # TCP segmentation
    'GRO',  # Generic receive
    'GSO',  # Generic segmentation
    'UFO',  # UDP Fragmentation
    'LRO',  # Large receive
    'LSO',  # Large send
    'TCS',  # TCP Checksum
    'UCS',  # UDP Checksum
    'SCS',  # SCTP Checksum
    'L2CRC',  # Layer-2 CRC
    'FDF',  # Intel Flow-Director Filter
    'RXVLAN',  # VLAN receive tunnel segmentation
    'TXVLAN',  # VLAN transmit tunnel segmentation
    'VXLAN',  # VxLAN tunneling
    'GRE',  # GRE tunneling
    'GENEVE',  # Geneve tunneling
    'TXUDP',  # UDP transmit tunnel segmentation
    'QINQ',  # QinQ specification
    'RDMA',  # remote direct memory access
    'RXHASH',  # receive hashing
    'RX',  # RX checksumming
    'TX',  # RX checksumming
    'SG',  # scatter-gather
    'SWITCHDEV',  # Offload datapath rules
]
