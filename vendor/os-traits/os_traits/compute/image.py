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

# This is fed from the list at
# https://docs.openstack.org/image-guide/image-formats.html#disk-formats
# and should be kept up to date with same.
TRAITS = [
    # Amazon kernel, machine, and ramdisk images
    'TYPE_AKI',
    'TYPE_AMI',
    'TYPE_ARI',

    # Optical media
    'TYPE_ISO',

    # Native format for QEMU
    'TYPE_QCOW2',

    # Unstructured generic byte-for-byte disk image
    'TYPE_RAW',

    # Native format for VirtualBox
    'TYPE_VDI',

    # VHD, VHDX disk (VMware, Xen, Microsoft, VirtualBox, etc)
    'TYPE_VHD',
    'TYPE_VHDX',

    # Native format for VMware
    'TYPE_VMDK',
]
