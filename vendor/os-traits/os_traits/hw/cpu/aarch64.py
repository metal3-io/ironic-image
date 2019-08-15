# -*- coding: utf-8 -*-
# Copyright 2017 Arm Limited.
#
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
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=9703d9d7f
    'FP',
    'ASIMD',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=46efe547a
    'EVTSTRM',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=4bff28ccd
    'AES',
    'PMULL',
    'SHA1',
    'SHA2',
    'CRC32',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=bf5006184
    'FPHP',
    'ASIMDHP',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=f92f5ce01
    'ASIMDRDM',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=40a1db243
    'ATOMICS',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=c8c3798d2
    'JSCVT',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=cb567e79f
    'FCMA',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=c651aae5a
    'LRCPC',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=7aac405eb
    'DCPOP',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=f5e035f86
    'SHA3',
    'SM3',
    'SM4',
    'ASIMDDP',
    'SHA512',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=43994d824
    'SVE',
    # ref: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/
    # linux.git/commit/?id=77c97b4ee
    'CPUID',
]
