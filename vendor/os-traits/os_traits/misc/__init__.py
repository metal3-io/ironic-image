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
    # Indicates that the resource provider decorated with this trait exposes
    # its resources for consumption on *other* resource providers via an
    # aggregate association. The canonical example here would be a shared
    # storage pool.
    #
    # The deployer might create a resource provider, let's call it "NFS_SHARE"
    # that has an inventory record of 2000 total DISK_GB resources.
    #
    # There may be 10 other resource providers, let's call them "CN_1" through
    # "CN_10" that represent compute nodes. These compute node resource
    # providers have inventory records for MEMORY_MB and VCPU resources, but no
    # DISK_GB inventory.
    #
    # Both the "NFS_SHARE" resource provider and each of the "CN_x" resource
    # providers are associated to the same aggregate, let's call it "AGG_A".
    #
    # Deployers would decorate the "NFS_SHARE" resource provider with the
    # "MISC_SHARES_VIA_AGGREGATE" trait to indicate to the system that the
    # DISK_GB inventory it provides can be consumed by consumers of resources
    # on any of the other resource providers associated with any aggregate
    # "NFS_SHARE" is associated to.
    'SHARES_VIA_AGGREGATE',
]
