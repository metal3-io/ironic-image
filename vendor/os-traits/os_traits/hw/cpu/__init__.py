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

# A few generalized capabilities of some RP
TRAITS = [
    # The resource provider decorated with this trait indicates that
    # hyperthreading is enabled on the provider.
    # Operators of resource-constrained systems would be able to decorate a
    # single NUMA node resource provider on a multi-socket system with this
    # HW_CPU_HYPERTHREADING trait to “carve out” a part of the host system
    # for guests that can tolerate hyperthread siblings providing CPU
    # resources.
    'HYPERTHREADING',
]
