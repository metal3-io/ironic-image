#!/usr/bin/env python3
"""Network interface detection helpers for ironic.

Uses ``ip -json -d`` for structured output, which correctly handles
cases where a MAC or IP address appears on multiple interfaces (e.g. a
physical interface enslaved to an OVS or Linux bridge).

Subcommands
-----------
interface-of-mac [<macs_csv>]  (default)
    Detect the provisioning interface.  *macs_csv* is a
    comma-separated list of MAC addresses; falls back to the
    PROVISIONING_MACS environment variable when omitted.

interface-of-ip <ip_address> [4|6]
    Return the interface that carries *ip_address*.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

# Type alias for the dict entries returned by ``ip -json``.
IfaceData = dict[str, Any]

# (interface_name, is_bridge, has_global_ip)
Candidate = tuple[str, bool, bool]


def _ip_json(*args: str) -> list[IfaceData]:
    """Run an ``ip -json -d`` command and return the parsed output."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        ["ip", "-json", "-d"] + list(args),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return []


def _iface_name(data: IfaceData) -> str:
    """Return the base interface name, stripping any ``@link`` suffix."""
    return data.get("ifname", "").split("@")[0]


def _is_bridge(data: IfaceData) -> bool:
    """Return True if the interface is a bridge (Linux bridge or OVS)."""
    kind: str = data.get("linkinfo", {}).get("info_kind", "")
    return kind in ("bridge", "openvswitch")


def _has_global_address(ifname: str, addr_data: list[IfaceData]) -> bool:
    """Return True if *ifname* carries at least one global-scope address."""
    for iface in addr_data:
        if _iface_name(iface) != ifname:
            continue
        for addr_info in iface.get("addr_info", []):
            if addr_info.get("scope") == "global":
                return True
    return False


# -- MAC-based detection ---------------------------------------------------

def find_by_mac(macs_csv: str) -> str | None:
    """Return the best UP interface whose MAC matches one in *macs_csv*.

    When a MAC appears on both a physical interface and a bridge (common
    with OVN-Kubernetes), the selection prefers:

    1. The interface that already carries a global IP address (this is
       the one dnsmasq should bind to).
    2. Otherwise, the non-bridge (physical) interface.
    3. As a last resort, the first match.
    """
    link_data: list[IfaceData] = _ip_json("link", "show", "up")
    addr_data: list[IfaceData] = _ip_json("addr", "show")

    for mac in macs_csv.split(","):
        mac = mac.strip().lower()
        if not mac:
            continue

        candidates: list[Candidate] = []
        for iface in link_data:
            if iface.get("address", "").lower() == mac:
                name: str = _iface_name(iface)
                bridge: bool = _is_bridge(iface)
                has_ip: bool = _has_global_address(name, addr_data)
                candidates.append((name, bridge, has_ip))

        if not candidates:
            continue

        if len(candidates) == 1:
            return candidates[0][0]

        with_ip: list[Candidate] = [c for c in candidates if c[2]]
        if len(with_ip) == 1:
            return with_ip[0][0]

        pool: list[Candidate] = with_ip or candidates
        physical: list[Candidate] = [c for c in pool if not c[1]]
        if physical:
            return physical[0][0]

        return pool[0][0]

    return None


def detect_provisioning_interface(macs_csv: str | None = None) -> str:
    """Return the name of the provisioning interface.

    *macs_csv* is a comma-separated list of MAC addresses to match.
    Falls back to the ``PROVISIONING_MACS`` environment variable when
    *macs_csv* is ``None`` or empty.
    """
    provisioning_macs: str = (
        macs_csv if macs_csv else os.environ.get("PROVISIONING_MACS", "")
    )

    interface: str = "provisioning"

    if provisioning_macs:
        found: str | None = find_by_mac(provisioning_macs)
        if found:
            interface = found

    return interface


# -- IP-based detection ----------------------------------------------------

_VALID_IP_VERSIONS: set[str] = {"4", "6"}
_VALID_SUBCOMMANDS: set[str | None] = {None, "interface-of-mac", "interface-of-ip"}


def find_by_ip(ip_addr: str, ip_version: str | None = None) -> str:
    """Return the first interface carrying *ip_addr*, or empty string.

    *ip_version* can be ``"4"`` or ``"6"`` to restrict the address
    family, or ``None`` to search both.

    Raises ``ValueError`` if *ip_version* is not ``None``, ``"4"``,
    or ``"6"``.
    """
    if ip_version is not None and ip_version not in _VALID_IP_VERSIONS:
        raise ValueError(
            f"ip_version must be '4', '6', or None, got {ip_version!r}")

    args: list[str] = ["addr", "show"]
    if ip_version:
        args = [f"-{ip_version}"] + args

    ip_bare: str = ip_addr.split("/")[0].lower()

    for iface in _ip_json(*args):
        for addr_info in iface.get("addr_info", []):
            if addr_info.get("local", "").lower() == ip_bare:
                return _iface_name(iface)
    return ""


# -- CLI entry point -------------------------------------------------------

_USAGE: str = (
    "Usage: detect_interface.py"
    " [interface-of-mac [<macs>] | interface-of-ip <addr> [4|6]]"
)


def main() -> None:
    subcommand: str | None = sys.argv[1] if len(sys.argv) >= 2 else None

    if subcommand not in _VALID_SUBCOMMANDS:
        print(f"ERROR: unknown subcommand {subcommand!r}\n{_USAGE}",
              file=sys.stderr)
        sys.exit(1)

    if subcommand == "interface-of-ip":
        if len(sys.argv) < 3:
            print(f"ERROR: interface-of-ip requires an IP address\n{_USAGE}",
                  file=sys.stderr)
            sys.exit(1)
        ip_addr: str = sys.argv[2]
        ip_version: str | None = sys.argv[3] if len(sys.argv) > 3 else None
        print(find_by_ip(ip_addr, ip_version))
    else:
        macs_csv: str | None = sys.argv[2] if len(sys.argv) > 2 else None
        print(detect_provisioning_interface(macs_csv))


if __name__ == "__main__":
    main()
