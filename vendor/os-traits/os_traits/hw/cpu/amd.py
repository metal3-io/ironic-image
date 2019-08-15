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
    # ref: https://docs.openstack.org/os-traits/latest/contributor/index.html#trait-lifecycle-policy # noqa
    # NOTE(kchamart): This file is deprecated.  The 'SEV' trait is
    # AMD-only, so it is copied to hw/cpu/amd.py; it is retained here
    # not to cause Placement breakage.  All AMD-only traits are being
    # tracked under: hw/cpu/x86/amd.py.  And the traits common to both
    # AMD _and_ Intel are being tracked here: hw/cpu/x86/__init__.py.
    #
    # NOTE(aspiers): This trait was never used for anything, since the
    # first bit of SEV code to use an SEV trait will land after this
    # https://review.opendev.org/#/c/638680/ which has an explicit
    # 'Depends-On' against the change I1c9a72d19ef ("hw: cpu: Rework the
    # directory layout; add missing traits"), and is actually blocked
    # until I1c9a72d19ef merges *and* gets released.
    'SEV',
]
