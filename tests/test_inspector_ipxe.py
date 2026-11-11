"""Unit tests for the inspector.ipxe.j2 template."""

import os
import unittest

import jinja2

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "ironic-config",
                        "inspector.ipxe.j2")

BASE_URL = "http://192.0.2.1:80"
IMAGES = "file:///shared/html/images"


def _render(**env):
    """Render the template the same way render_j2_config does."""
    env.setdefault("IRONIC_IPA_BASE_URL", BASE_URL)
    env.setdefault("IRONIC_IPA_COLLECTORS", "default")
    env.setdefault("IRONIC_ENABLE_VLAN_INTERFACES", "all")
    env.setdefault("INSPECTOR_EXTRA_ARGS", "")
    env.setdefault("IRONIC_KERNEL_PARAMS", "")
    with open(TEMPLATE, encoding="utf-8") as f:
        return jinja2.Template(f.read()).render(env=env)


def _by_arch(*arches):
    """Return DEPLOY_{KERNEL,RAMDISK}_BY_ARCH values for *arches*."""
    kernels = ",".join(
        f"{a}:{IMAGES}/ironic-python-agent_{a}.kernel" for a in arches)
    ramdisks = ",".join(
        f"{a}:{IMAGES}/ironic-python-agent_{a}.initramfs" for a in arches)
    return {"DEPLOY_KERNEL_BY_ARCH": kernels,
            "DEPLOY_RAMDISK_BY_ARCH": ramdisks}


class TestInspectorIpxeByArch(unittest.TestCase):

    def test_both_arches(self):
        out = _render(**_by_arch("x86_64", "aarch64"))
        self.assertIn("iseq ${buildarch} arm64 && goto arm64 ||", out)
        self.assertIn("iseq ${buildarch} x86_64 && goto x86_64 ||", out)
        self.assertIn(
            f"set ipa_kernel {BASE_URL}/images/"
            "ironic-python-agent_aarch64.kernel", out)
        self.assertIn(
            f"set ipa_kernel {BASE_URL}/images/"
            "ironic-python-agent_x86_64.kernel", out)

    def test_missing_arch_uses_fallback(self):
        out = _render(**_by_arch("aarch64"))
        self.assertIn("iseq ${buildarch} arm64 && goto arm64 ||", out)
        self.assertNotIn("goto x86_64", out)
        self.assertIn("goto fallback", out)

    def test_arch_without_ramdisk_uses_fallback(self):
        env = _by_arch("x86_64", "aarch64")
        env["DEPLOY_RAMDISK_BY_ARCH"] = (
            f"x86_64:{IMAGES}/ironic-python-agent_x86_64.initramfs")
        out = _render(**env)
        self.assertNotIn("goto arm64", out)
        self.assertIn("iseq ${buildarch} x86_64 && goto x86_64 ||", out)

    def test_without_by_arch(self):
        out = _render()
        self.assertNotIn("buildarch", out)
        self.assertIn(
            f"initrd --timeout 60000 {BASE_URL}/images/"
            "ironic-python-agent.initramfs", out)


if __name__ == "__main__":
    unittest.main()
