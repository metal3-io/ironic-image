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
    # traits corresponding to the allowed values of "hw_disk_bus"
    # and "hw_cdrom_bus" image metadata properties
    # https://github.com/openstack/nova/blob/1f74441/nova/objects/fields.py#L320-L332
    'BUS_FDC',
    'BUS_IDE',
    'BUS_LXC',
    'BUS_SATA',
    'BUS_SCSI',
    'BUS_USB',
    'BUS_VIRTIO',
    'BUS_UML',
    'BUS_XEN',
]
