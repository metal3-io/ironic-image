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
    # ref: https://en.wikipedia.org/wiki/CUDA
    # ref: https://developer.nvidia.com/cuda-toolkit-archive
    'COMPUTE_CAPABILITY_V1_0',
    'COMPUTE_CAPABILITY_V1_1',
    'COMPUTE_CAPABILITY_V1_2',
    'COMPUTE_CAPABILITY_V1_3',
    'COMPUTE_CAPABILITY_V2_0',
    'COMPUTE_CAPABILITY_V2_1',
    'COMPUTE_CAPABILITY_V3_0',
    'COMPUTE_CAPABILITY_V3_2',
    'COMPUTE_CAPABILITY_V3_5',
    'COMPUTE_CAPABILITY_V3_7',
    'COMPUTE_CAPABILITY_V5_0',
    'COMPUTE_CAPABILITY_V5_2',
    'COMPUTE_CAPABILITY_V5_3',
    'COMPUTE_CAPABILITY_V6_0',
    'COMPUTE_CAPABILITY_V6_1',
    'COMPUTE_CAPABILITY_V6_2',
    'COMPUTE_CAPABILITY_V7_0',
    'COMPUTE_CAPABILITY_V7_1',
    'COMPUTE_CAPABILITY_V7_2',
    'SDK_V6_5',
    'SDK_V7_5',
    'SDK_V8_0',
    'SDK_V9_0',
    'SDK_V9_1',
    'SDK_V9_2',
    'SDK_V10_0',
]

_CAPS_V1 = [
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V1_0',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V1_1',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V1_2',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V1_3',
]

_CAPS_V2 = [
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V2_0',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V2_1',
]

_CAPS_V3 = [
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V3_0',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V3_2',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V3_5',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V3_7',
]

_CAPS_V5 = [
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V5_0',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V5_2',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V5_3',
]

_CAPS_V6 = [
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V6_0',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V6_1',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V6_2',
]

_CAPS_V7 = [
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V7_0',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V7_1',
    'HW_GPU_CUDA_COMPUTE_CAPABILITY_V7_2',
]

_SDK_COMPUTE_CAP_SUPPORT = {
    'HW_GPU_CUDA_SDK_V6_5': set(
        _CAPS_V1 + _CAPS_V2 + _CAPS_V3 + _CAPS_V5
    ),
    'HW_GPU_CUDA_SDK_V7_5': set(
        _CAPS_V2 + _CAPS_V3 + _CAPS_V5
    ),
    'HW_GPU_CUDA_SDK_V8_0': set(
        _CAPS_V2 + _CAPS_V3 + _CAPS_V5 + _CAPS_V6
    ),
    'HW_GPU_CUDA_SDK_V9_0': set(
        _CAPS_V3 + _CAPS_V5 + _CAPS_V6 + _CAPS_V7
    ),
    'HW_GPU_CUDA_SDK_V9_1': set(
        _CAPS_V3 + _CAPS_V5 + _CAPS_V6 + _CAPS_V7
    ),
    'HW_GPU_CUDA_SDK_V9_2': set(
        _CAPS_V3 + _CAPS_V5 + _CAPS_V6 + _CAPS_V7
    ),
    'HW_GPU_CUDA_SDK_V10_0': set(
        _CAPS_V3 + _CAPS_V5 + _CAPS_V6 + _CAPS_V7
    ),
}


def compute_capabilities_supported(sdk_trait):
    """Given an SDK trait, returns a set of compute capability traits that the
    version of the SDK supports.

    Returns None if no matches were found for the SDK trait.
    """
    return _SDK_COMPUTE_CAP_SUPPORT.get(sdk_trait)
