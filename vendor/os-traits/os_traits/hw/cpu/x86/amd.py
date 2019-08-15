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
    # ref: http://specs.openstack.org/openstack/nova-specs/specs/train/approved/amd-sev-libvirt-support.html # noqa
    'SEV',
    # ref: https://en.wikipedia.org/wiki/AMD-V
    'SVM',
    # ref: https://git.qemu.org/?p=qemu.git;a=blob;f=docs/qemu-cpu-models.texi
    # (Important CPU features for AMD x86 hosts)
    'IBPB',
    'NO_SSB',
    'SSBD',
    'VIRT_SSBD',
]
