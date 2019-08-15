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

from os_traits.hw.gpu import cuda
from os_traits.tests import base


class TestCUDA(base.TestCase):

    def test_unknown_sdk_support(self):
        self.assertIsNone(cuda.compute_capabilities_supported('UNKNOWN'))

    def test_sdk6_5_support(self):
        expected = set([
            cuda.COMPUTE_CAPABILITY_V1_0,
            cuda.COMPUTE_CAPABILITY_V1_1,
            cuda.COMPUTE_CAPABILITY_V1_2,
            cuda.COMPUTE_CAPABILITY_V1_3,
            cuda.COMPUTE_CAPABILITY_V2_0,
            cuda.COMPUTE_CAPABILITY_V2_1,
            cuda.COMPUTE_CAPABILITY_V3_0,
            cuda.COMPUTE_CAPABILITY_V3_2,
            cuda.COMPUTE_CAPABILITY_V3_5,
            cuda.COMPUTE_CAPABILITY_V3_7,
            cuda.COMPUTE_CAPABILITY_V5_0,
            cuda.COMPUTE_CAPABILITY_V5_2,
            cuda.COMPUTE_CAPABILITY_V5_3,
        ])

        actual = cuda.compute_capabilities_supported(cuda.SDK_V6_5)
        self.assertEqual(expected, actual)
