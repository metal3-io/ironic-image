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
    # The virt driver supports attaching a volume after boot
    'ATTACH',
    # The virt driver supports attaching a volume after boot and specifying a
    # device tag for the volume
    'ATTACH_WITH_TAG',
    # The virt driver supports extending a volume after boot
    'EXTEND',
    # The virt driver supports volumes that can be attached to multiple guests
    'MULTI_ATTACH',
]
