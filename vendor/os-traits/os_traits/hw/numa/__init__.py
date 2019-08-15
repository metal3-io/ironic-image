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

# Characteristics of NUMA nodes/cells/sockets/etc.
TRAITS = [
    # A provider representing the subtree root of a NUMA node should be
    # decorated with this trait so that requests can represent NUMA affinity
    # even when no resources are requested from the NUMA node provider itself.
    # See https://review.opendev.org/#/c/662191/
    'ROOT',
]
