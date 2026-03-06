"""Unit tests for detect_interface.py."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import detect_interface


def _link_entry(ifname, mac, up=True, kind=None):
    """Build a minimal ``ip -json -d link show`` entry."""
    entry = {
        "ifname": ifname,
        "address": mac,
        "operstate": "UP" if up else "DOWN",
    }
    if kind:
        entry["linkinfo"] = {"info_kind": kind}
    return entry


def _addr_entry(ifname, *addrs):
    """Build a minimal ``ip -json addr show`` entry.

    Each element in *addrs* is ``(ip, scope)`` — e.g.
    ``("192.168.1.10", "global")``.
    """
    return {
        "ifname": ifname,
        "addr_info": [
            {"local": ip, "scope": scope} for ip, scope in addrs
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestIsBridge(unittest.TestCase):

    def test_linux_bridge(self):
        data = {"linkinfo": {"info_kind": "bridge"}}
        self.assertTrue(detect_interface._is_bridge(data))

    def test_ovs_bridge(self):
        data = {"linkinfo": {"info_kind": "openvswitch"}}
        self.assertTrue(detect_interface._is_bridge(data))

    def test_physical(self):
        data = {"linkinfo": {"info_kind": ""}}
        self.assertFalse(detect_interface._is_bridge(data))

    def test_no_linkinfo(self):
        self.assertFalse(detect_interface._is_bridge({}))


class TestIfaceName(unittest.TestCase):

    def test_plain_name(self):
        self.assertEqual(
            detect_interface._iface_name({"ifname": "eth0"}), "eth0")

    def test_at_suffix_stripped(self):
        self.assertEqual(
            detect_interface._iface_name({"ifname": "eno1@br-ex"}), "eno1")


class TestHasGlobalAddress(unittest.TestCase):

    def test_has_global(self):
        addr_data = [_addr_entry("eth0", ("10.0.0.1", "global"))]
        self.assertTrue(
            detect_interface._has_global_address("eth0", addr_data))

    def test_only_link_local(self):
        addr_data = [_addr_entry("eth0", ("fe80::1", "link"))]
        self.assertFalse(
            detect_interface._has_global_address("eth0", addr_data))

    def test_wrong_interface(self):
        addr_data = [_addr_entry("eth1", ("10.0.0.1", "global"))]
        self.assertFalse(
            detect_interface._has_global_address("eth0", addr_data))


# ---------------------------------------------------------------------------
# find_by_mac
# ---------------------------------------------------------------------------

def _patch_ip_json(link_data, addr_data):
    """Return a patcher that feeds *link_data* and *addr_data* to _ip_json."""
    def fake_ip_json(*args):
        if "link" in args:
            return link_data
        return addr_data
    return mock.patch.object(detect_interface, "_ip_json", side_effect=fake_ip_json)


class TestFindByMac(unittest.TestCase):

    def test_single_match(self):
        link = [_link_entry("eth0", "aa:bb:cc:dd:ee:ff")]
        addr = [_addr_entry("eth0", ("10.0.0.1", "global"))]
        with _patch_ip_json(link, addr):
            self.assertEqual(
                detect_interface.find_by_mac("aa:bb:cc:dd:ee:ff"), "eth0")

    def test_no_match_returns_none(self):
        link = [_link_entry("eth0", "aa:bb:cc:dd:ee:ff")]
        addr = []
        with _patch_ip_json(link, addr):
            self.assertIsNone(
                detect_interface.find_by_mac("11:22:33:44:55:66"))

    def test_case_insensitive(self):
        link = [_link_entry("eth0", "aa:bb:cc:dd:ee:ff")]
        addr = []
        with _patch_ip_json(link, addr):
            self.assertEqual(
                detect_interface.find_by_mac("AA:BB:CC:DD:EE:FF"), "eth0")

    def test_multiple_macs_first_hit_wins(self):
        link = [_link_entry("eth1", "11:22:33:44:55:66")]
        addr = []
        with _patch_ip_json(link, addr):
            self.assertEqual(
                detect_interface.find_by_mac(
                    "aa:bb:cc:dd:ee:ff,11:22:33:44:55:66"),
                "eth1")

    def test_prefers_interface_with_ip(self):
        """The bug scenario: eno1 and br-ex share a MAC; br-ex has the IP."""
        mac = "6c:92:cf:0d:03:e6"
        link = [
            _link_entry("eno1@br-ex", mac),
            _link_entry("br-ex", mac, kind="openvswitch"),
        ]
        addr = [
            _addr_entry("eno1"),
            _addr_entry("br-ex", ("192.168.111.10", "global")),
        ]
        with _patch_ip_json(link, addr):
            self.assertEqual(detect_interface.find_by_mac(mac), "br-ex")

    def test_prefers_physical_when_no_ip(self):
        """No interface has an IP yet — prefer physical over bridge."""
        mac = "6c:92:cf:0d:03:e6"
        link = [
            _link_entry("eno1@br-ex", mac),
            _link_entry("br-ex", mac, kind="bridge"),
        ]
        addr = [
            _addr_entry("eno1"),
            _addr_entry("br-ex"),
        ]
        with _patch_ip_json(link, addr):
            self.assertEqual(detect_interface.find_by_mac(mac), "eno1")

    def test_prefers_physical_with_ip_over_bridge_with_ip(self):
        """Both have IPs — prefer physical."""
        mac = "aa:bb:cc:dd:ee:ff"
        link = [
            _link_entry("eno1@br-ex", mac),
            _link_entry("br-ex", mac, kind="openvswitch"),
        ]
        addr = [
            _addr_entry("eno1", ("10.0.0.1", "global")),
            _addr_entry("br-ex", ("10.0.0.1", "global")),
        ]
        with _patch_ip_json(link, addr):
            self.assertEqual(detect_interface.find_by_mac(mac), "eno1")

    def test_falls_back_to_bridge_if_only_bridges(self):
        mac = "aa:bb:cc:dd:ee:ff"
        link = [
            _link_entry("br0", mac, kind="bridge"),
            _link_entry("br1", mac, kind="openvswitch"),
        ]
        addr = [_addr_entry("br0"), _addr_entry("br1")]
        with _patch_ip_json(link, addr):
            self.assertEqual(detect_interface.find_by_mac(mac), "br0")

    def test_empty_macs(self):
        link = [_link_entry("eth0", "aa:bb:cc:dd:ee:ff")]
        addr = []
        with _patch_ip_json(link, addr):
            self.assertIsNone(detect_interface.find_by_mac(""))
            self.assertIsNone(detect_interface.find_by_mac(",,,"))


# ---------------------------------------------------------------------------
# detect_provisioning_interface
# ---------------------------------------------------------------------------

class TestDetectProvisioningInterface(unittest.TestCase):

    @mock.patch.object(detect_interface, "find_by_mac", return_value="eth0")
    def test_explicit_macs_argument(self, mock_find):
        self.assertEqual(
            detect_interface.detect_provisioning_interface(
                "aa:bb:cc:dd:ee:ff"), "eth0")
        mock_find.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @mock.patch.dict("os.environ", {"PROVISIONING_MACS": "aa:bb:cc:dd:ee:ff"})
    @mock.patch.object(detect_interface, "find_by_mac", return_value="eth0")
    def test_falls_back_to_env_var(self, mock_find):
        self.assertEqual(
            detect_interface.detect_provisioning_interface(), "eth0")
        mock_find.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    @mock.patch.dict("os.environ", {"PROVISIONING_MACS": "aa:bb:cc:dd:ee:ff"})
    @mock.patch.object(detect_interface, "find_by_mac", return_value=None)
    def test_defaults_to_provisioning(self, _mock):
        self.assertEqual(
            detect_interface.detect_provisioning_interface(), "provisioning")

    @mock.patch.dict("os.environ", {}, clear=True)
    def test_no_macs_defaults_to_provisioning(self):
        self.assertEqual(
            detect_interface.detect_provisioning_interface(), "provisioning")

    @mock.patch.dict("os.environ", {"PROVISIONING_MACS": "from:env:only"})
    @mock.patch.object(detect_interface, "find_by_mac", return_value="eth1")
    def test_explicit_arg_overrides_env(self, mock_find):
        self.assertEqual(
            detect_interface.detect_provisioning_interface(
                "from:cli:arg"), "eth1")
        mock_find.assert_called_once_with("from:cli:arg")


# ---------------------------------------------------------------------------
# find_by_ip
# ---------------------------------------------------------------------------

class TestFindByIp(unittest.TestCase):

    def test_match(self):
        addr = [_addr_entry("eth0", ("192.168.1.10", "global"))]
        with mock.patch.object(
                detect_interface, "_ip_json", return_value=addr):
            self.assertEqual(
                detect_interface.find_by_ip("192.168.1.10"), "eth0")

    def test_no_match_returns_empty(self):
        addr = [_addr_entry("eth0", ("192.168.1.10", "global"))]
        with mock.patch.object(
                detect_interface, "_ip_json", return_value=addr):
            self.assertEqual(
                detect_interface.find_by_ip("10.0.0.99"), "")

    def test_strips_prefix_length(self):
        addr = [_addr_entry("eth0", ("192.168.1.10", "global"))]
        with mock.patch.object(
                detect_interface, "_ip_json", return_value=addr):
            self.assertEqual(
                detect_interface.find_by_ip("192.168.1.10/24"), "eth0")

    def test_case_insensitive_ipv6(self):
        addr = [_addr_entry("eth0", ("fd00::1", "global"))]
        with mock.patch.object(
                detect_interface, "_ip_json", return_value=addr):
            self.assertEqual(
                detect_interface.find_by_ip("FD00::1"), "eth0")

    def test_ip_version_passed_to_ip_json(self):
        with mock.patch.object(
                detect_interface, "_ip_json", return_value=[]) as m:
            detect_interface.find_by_ip("10.0.0.1", ip_version="4")
            m.assert_called_once_with("-4", "addr", "show")

    def test_strips_at_suffix(self):
        addr = [_addr_entry("eno1@br-ex", ("10.0.0.1", "global"))]
        with mock.patch.object(
                detect_interface, "_ip_json", return_value=addr):
            self.assertEqual(
                detect_interface.find_by_ip("10.0.0.1"), "eno1")

    def test_invalid_ip_version_raises(self):
        with self.assertRaises(ValueError):
            detect_interface.find_by_ip("10.0.0.1", ip_version="5")

    def test_valid_ip_versions_accepted(self):
        with mock.patch.object(
                detect_interface, "_ip_json", return_value=[]):
            detect_interface.find_by_ip("10.0.0.1", ip_version="4")
            detect_interface.find_by_ip("10.0.0.1", ip_version="6")
            detect_interface.find_by_ip("10.0.0.1", ip_version=None)


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):

    @mock.patch.object(detect_interface, "detect_provisioning_interface",
                       return_value="eth0")
    def test_default_subcommand(self, _mock):
        with mock.patch("sys.argv", ["detect_interface.py"]):
            with mock.patch("builtins.print") as mock_print:
                detect_interface.main()
                mock_print.assert_called_once_with("eth0")

    @mock.patch.object(detect_interface, "find_by_ip", return_value="eno1")
    def test_interface_of_ip_subcommand(self, mock_find):
        with mock.patch("sys.argv",
                        ["detect_interface.py", "interface-of-ip",
                         "10.0.0.1", "4"]):
            with mock.patch("builtins.print") as mock_print:
                detect_interface.main()
                mock_find.assert_called_once_with("10.0.0.1", "4")
                mock_print.assert_called_once_with("eno1")

    def test_interface_of_ip_missing_addr_exits(self):
        with mock.patch("sys.argv",
                        ["detect_interface.py", "interface-of-ip"]):
            with self.assertRaises(SystemExit) as ctx:
                detect_interface.main()
            self.assertEqual(ctx.exception.code, 1)

    @mock.patch.object(detect_interface, "detect_provisioning_interface",
                       return_value="eth0")
    def test_explicit_interface_of_mac_with_arg(self, mock_detect):
        with mock.patch("sys.argv",
                        ["detect_interface.py", "interface-of-mac",
                         "aa:bb:cc:dd:ee:ff"]):
            with mock.patch("builtins.print") as mock_print:
                detect_interface.main()
                mock_detect.assert_called_once_with("aa:bb:cc:dd:ee:ff")
                mock_print.assert_called_once_with("eth0")

    @mock.patch.object(detect_interface, "detect_provisioning_interface",
                       return_value="eth0")
    def test_explicit_interface_of_mac_no_arg(self, mock_detect):
        with mock.patch("sys.argv",
                        ["detect_interface.py", "interface-of-mac"]):
            with mock.patch("builtins.print") as mock_print:
                detect_interface.main()
                mock_detect.assert_called_once_with(None)
                mock_print.assert_called_once_with("eth0")

    def test_unknown_subcommand_exits(self):
        with mock.patch("sys.argv",
                        ["detect_interface.py", "interface-of-Ip"]):
            with self.assertRaises(SystemExit) as ctx:
                detect_interface.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_garbage_argument_exits(self):
        with mock.patch("sys.argv",
                        ["detect_interface.py", "foobar"]):
            with self.assertRaises(SystemExit) as ctx:
                detect_interface.main()
            self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
