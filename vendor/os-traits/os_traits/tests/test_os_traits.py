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

import re

import os_traits as ot
from os_traits.hw.cpu import x86
from os_traits.hw.gpu import api
from os_traits.hw.gpu import resolution
from os_traits.hw.nic import offload
from os_traits.tests import base


class TestSymbols(base.TestCase):

    def test_trait(self):
        """Simply tests that the constants from submodules are imported into
        the primary os_traits module space.
        """
        trait = ot.HW_CPU_X86_SSE42
        self.assertEqual("HW_CPU_X86_SSE42", trait)

        # And the "leaf-module" namespace...
        self.assertEqual(x86.SSE42, ot.HW_CPU_X86_SSE42)
        self.assertEqual(api.DIRECTX_V10, ot.HW_GPU_API_DIRECTX_V10)
        self.assertEqual(resolution.W1920H1080,
                         ot.HW_GPU_RESOLUTION_W1920H1080)
        self.assertEqual(offload.TSO, ot.HW_NIC_OFFLOAD_TSO)

    def test_get_traits_filter_by_prefix(self):
        traits = ot.get_traits('HW_CPU')
        self.assertIn("HW_CPU_X86_SSE42", traits)
        self.assertIn("HW_CPU_HYPERTHREADING", traits)
        self.assertIn(ot.HW_CPU_X86_AVX2, traits)
        self.assertNotIn(ot.STORAGE_DISK_SSD, traits)
        self.assertNotIn(ot.HW_NIC_SRIOV, traits)
        self.assertNotIn('CUSTOM_NAMESPACE', traits)
        self.assertNotIn('os_traits', traits)

    def test_dunderinit_and_nondunderinit(self):
        """Make sure we can have both dunderinit'd traits and submodules
        co-exist in the same namespace.
        """
        traits = ot.get_traits('COMPUTE')
        self.assertIn("COMPUTE_DEVICE_TAGGING", traits)
        self.assertIn(ot.COMPUTE_DEVICE_TAGGING, traits)
        self.assertIn("COMPUTE_VOLUME_EXTEND", traits)
        self.assertIn(ot.COMPUTE_NET_ATTACH_INTERFACE, traits)

    def test_get_traits_filter_by_suffix(self):
        traits = ot.get_traits(suffix='SSE42')
        self.assertIn("HW_CPU_X86_SSE42", traits)
        self.assertEqual(1, len(traits))

    def test_get_traits_filter_by_prefix_and_suffix(self):
        traits = ot.get_traits(prefix='HW_NIC', suffix='RSA')
        self.assertIn("HW_NIC_ACCEL_RSA", traits)
        self.assertNotIn(ot.HW_NIC_ACCEL_TLS, traits)
        self.assertEqual(1, len(traits))

        traits = ot.get_traits(prefix='HW_NIC', suffix='TX')
        self.assertIn("HW_NIC_SRIOV_QOS_TX", traits)
        self.assertIn("HW_NIC_OFFLOAD_TX", traits)
        self.assertEqual(2, len(traits))

    def test_check_traits(self):
        traits = set(["HW_CPU_X86_SSE42", "HW_CPU_X86_XOP"])
        not_traits = set(["not_trait1", "not_trait2"])

        check_traits = []
        check_traits.extend(traits)
        check_traits.extend(not_traits)
        self.assertEqual((traits, not_traits),
                         ot.check_traits(check_traits))

    def test_check_traits_filter_by_prefix(self):
        hw_trait = "HW_CPU_X86_SSE42"
        storage_trait = "STORAGE_DISK_SSD"

        check_traits = [hw_trait, storage_trait]
        self.assertEqual((set([hw_trait]), set([storage_trait])),
                         ot.check_traits(check_traits, "HW"))
        self.assertEqual((set([storage_trait]), set([hw_trait])),
                         ot.check_traits(check_traits, "STORAGE"))
        self.assertEqual((set(), set([hw_trait, storage_trait])),
                         ot.check_traits(check_traits, "MISC"))

    def test_is_custom(self):
        self.assertTrue(ot.is_custom('CUSTOM_FOO'))
        self.assertFalse(ot.is_custom('HW_CPU_X86_SSE42'))

    def test_trait_names_match_regex(self):
        traits = ot.get_traits()
        valid_name = re.compile("^[A-Z][A-Z0-9_]*$")
        for t in traits:
            match = valid_name.match(t)
            if not match:
                self.fail("Trait %s does not validate name regex." % t)

    def test_normalize_name(self):
        values = [
            ("foo", "CUSTOM_FOO"),
            ("VCPU", "CUSTOM_VCPU"),
            ("CUSTOM_BOB", "CUSTOM_CUSTOM_BOB"),
            ("CUSTM_BOB", "CUSTOM_CUSTM_BOB"),
            (u"Fu\xdfball", u"CUSTOM_FU_BALL"),
            ("abc-123", "CUSTOM_ABC_123"),
            ("Hello, world!  This is a test ^_^",
             "CUSTOM_HELLO_WORLD_THIS_IS_A_TEST_"),
            ("  leading and trailing spaces  ",
             "CUSTOM__LEADING_AND_TRAILING_SPACES_"),
        ]
        for test_value, expected in values:
            result = ot.normalize_name(test_value)
            self.assertEqual(expected, result)
