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
    # Individual virtual functions can restrict transmit rates
    'QOS_TX',
    # Individual virtual functions can restrict receive rates
    'QOS_RX',
    # Individual virtual functions can set up multiple receive and transmit
    # queues for receive-side scaling
    'MULTIQUEUE',
    # If associated with a resource provider representing a physical function,
    # all VFs on the PF are marked as trusted. If set on a resource provider
    # representing a single virtual function, the VF is individually marked as
    # trusted.
    'TRUSTED',
]
