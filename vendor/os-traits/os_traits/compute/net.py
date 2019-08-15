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
    # The virt driver supports attaching a network interface after boot
    'ATTACH_INTERFACE',
    # The virt driver supports attaching a network interface after boot and
    # specifying a device tag for the interface
    'ATTACH_INTERFACE_WITH_TAG',

    # traits corresponding to the allowed values of "hw_vif_model"
    # image metadata property
    # https://github.com/openstack/nova/blob/1f74441/nova/network/model.py#L136-L149
    'VIF_MODEL_E1000',
    'VIF_MODEL_E1000E',
    'VIF_MODEL_LAN9118',
    'VIF_MODEL_NETFRONT',
    'VIF_MODEL_NE2K_PCI',
    'VIF_MODEL_PCNET',
    'VIF_MODEL_RTL8139',
    'VIF_MODEL_SPAPR_VLAN',
    'VIF_MODEL_SRIOV',
    'VIF_MODEL_VIRTIO',
    'VIF_MODEL_VMXNET',
    'VIF_MODEL_VMXNET3',
]
