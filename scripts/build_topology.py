#!/usr/bin/env python3
"""Build Lab 4 .pkt topologies (working + broken variants).

Requires the pt_codec package from https://github.com/w4lven/claude-to-packet-tracer
(cloned to /tmp/ctt in the original build; adjust PT_CODEC_SRC below).

Usage:
    python3 scripts/build_topology.py

Output:
    Lab-4-ACL-NAT-Internet-Edge.pkt          (working lab)
    Lab-4-ACL-NAT-Internet-Edge-BROKEN.pkt   (fault injected: PC-User2 has a
                                             wrong default gateway for the
                                             troubleshooting exercise)
"""
from __future__ import annotations

import sys
from pathlib import Path

PT_CODEC_SRC = Path("/tmp/ctt/src")          # pip-free import of pt_codec
LIBRARY_DIR = Path("/tmp/ctt/samples/library")
SKELETON_PKT = Path("/tmp/ctt/samples/template.pkt")

sys.path.insert(0, str(PT_CODEC_SRC))

from pt_codec import Topology  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Device configs (also mirrored under configs/ as paste-ready text files)
# ---------------------------------------------------------------------------

EDGE_ROUTER_CONFIG = """!
! Lab 4 - Internet Edge Router : PAT (NAT overload) + extended ACL
! Inside : 192.168.10.0/24  |  Outside : 203.0.113.0/30 (to ISP)
!
hostname Edge-Router
!
no ip domain-lookup
!
interface GigabitEthernet0/0/0
 description *** INSIDE - LAN 192.168.10.0/24 ***
 ip address 192.168.10.1 255.255.255.0
 ip nat inside
 ip access-group 101 in
 no shutdown
!
interface GigabitEthernet0/0/1
 description *** OUTSIDE - ISP 203.0.113.0/30 ***
 ip address 203.0.113.1 255.255.255.252
 ip nat outside
 no shutdown
!
interface GigabitEthernet0/0/2
 description *** UNUSED ***
 shutdown
!
! Default route toward the ISP - the "internet edge"
ip route 0.0.0.0 0.0.0.0 203.0.113.2
!
! === NAT overload (PAT) ===
! Every LAN address is translated to the outside interface address.
access-list 1 permit 192.168.10.0 0.0.0.255
ip nat inside source list 1 interface GigabitEthernet0/0/1 overload
!
! === Internet-edge extended ACL 101 (inbound on the inside interface) ===
! 1. Business traffic: web in, DNS + ping for ops
access-list 101 permit tcp 192.168.10.0 0.0.0.255 any eq 80
access-list 101 permit tcp 192.168.10.0 0.0.0.255 any eq 443
access-list 101 permit udp 192.168.10.0 0.0.0.255 any eq 53
access-list 101 permit icmp 192.168.10.0 0.0.0.255 any
! 2. Explicit denies: Telnet anywhere, restricted subnet everywhere
access-list 101 deny tcp any any eq 23
access-list 101 deny ip 192.168.10.128 0.0.0.127 any
! 3. Permit everything else the business needs
access-list 101 permit ip any any
!
end
"""

ISP_ROUTER_CONFIG = """!
! Lab 4 - Simulated ISP router.
! NOTE: no static route back to 192.168.10.0/24 is configured on purpose.
! NAT overload on Edge-Router hides every LAN address behind 203.0.113.1,
! exactly like a real ISP that only knows your public address.
!
hostname ISP-Router
!
no ip domain-lookup
!
interface GigabitEthernet0/0/0
 description *** to Edge-Router 203.0.113.0/30 ***
 ip address 203.0.113.2 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/0/1
 description *** Simulated Internet 198.51.100.0/24 ***
 ip address 198.51.100.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/0/2
 description *** UNUSED ***
 shutdown
!
end
"""

LAN_SWITCH_CONFIG = """!
! Lab 4 - LAN access switch (plain L2, all ports VLAN 1)
!
hostname LAN-Switch
!
interface FastEthernet0/1
 description *** PC-User1 ***
 switchport mode access
 spanning-tree portfast
!
interface FastEthernet0/2
 description *** PC-User2 ***
 switchport mode access
 spanning-tree portfast
!
interface FastEthernet0/3
 description *** PC-Restricted (denied subnet demo) ***
 switchport mode access
 spanning-tree portfast
!
interface FastEthernet0/24
 description *** Uplink to Edge-Router G0/0/0 ***
 switchport mode access
!
end
"""

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(broken: bool = False) -> Topology:
    t = Topology.open(SKELETON_PKT)
    t.clear()  # blank canvas, keeps PT version metadata

    # ---- devices (x, y = logical workspace coordinates) ----
    t.add_device_by_model(LIBRARY_DIR, "ISR4331", "Edge-Router", x=350, y=220)
    t.add_device_by_model(LIBRARY_DIR, "ISR4331", "ISP-Router", x=650, y=220)
    t.add_device_by_model(LIBRARY_DIR, "2960-24TT", "LAN-Switch", x=350, y=420)
    t.add_device_by_model(LIBRARY_DIR, "PC-PT", "PC-User1", x=150, y=580)
    t.add_device_by_model(LIBRARY_DIR, "PC-PT", "PC-User2", x=350, y=580)
    t.add_device_by_model(LIBRARY_DIR, "PC-PT", "PC-Restricted", x=550, y=580)
    t.add_device_by_model(LIBRARY_DIR, "Server-PT", "Web-Server", x=650, y=420)

    # ---- links ----
    # LAN side (straight-through copper)
    t.add_link("LAN-Switch", "FastEthernet0/1", "PC-User1", "FastEthernet0")
    t.add_link("LAN-Switch", "FastEthernet0/2", "PC-User2", "FastEthernet0")
    t.add_link("LAN-Switch", "FastEthernet0/3", "PC-Restricted", "FastEthernet0")
    t.add_link("LAN-Switch", "FastEthernet0/24", "Edge-Router", "GigabitEthernet0/0/0")
    # Edge link (crossover, router to router)
    t.add_link("Edge-Router", "GigabitEthernet0/0/1",
               "ISP-Router", "GigabitEthernet0/0/0",
               cable_type="eCopperCrossOver")
    # Simulated-internet side
    t.add_link("ISP-Router", "GigabitEthernet0/0/1", "Web-Server", "FastEthernet0")

    # ---- network-layer configs ----
    t.set_running_config("Edge-Router", EDGE_ROUTER_CONFIG)
    t.set_running_config("ISP-Router", ISP_ROUTER_CONFIG)
    t.set_running_config("LAN-Switch", LAN_SWITCH_CONFIG)

    # ---- end-device IP plans ----
    t.set_pc_network("PC-User1", ip="192.168.10.10",
                     mask="255.255.255.0", gateway="192.168.10.1")
    # The deliberate fault for the troubleshooting exercise:
    t.set_pc_network("PC-User2", ip="192.168.10.11",
                     mask="255.255.255.0",
                     gateway="192.168.10.254" if broken else "192.168.10.1")
    t.set_pc_network("PC-Restricted", ip="192.168.10.200",
                     mask="255.255.255.0", gateway="192.168.10.1")
    t.set_pc_network("Web-Server", ip="198.51.100.10",
                     mask="255.255.255.0", gateway="198.51.100.1")
    return t


def verify(t: Topology, broken: bool) -> None:
    """Sanity checks on the in-memory topology before saving."""
    names = {d.name for d in t.list_devices()}
    expected = {"Edge-Router", "ISP-Router", "LAN-Switch",
                "PC-User1", "PC-User2", "PC-Restricted", "Web-Server"}
    assert expected <= names, f"missing devices: {expected - names}"
    assert len(t.list_links()) == 6, f"expected 6 links, got {len(t.list_links())}"
    edge = t.get_running_config("Edge-Router")
    for needle in ["ip nat inside", "ip nat outside", "overload",
                   "ip access-group 101 in", "deny tcp any any eq 23",
                   "deny ip 192.168.10.128 0.0.0.127 any",
                   "ip route 0.0.0.0 0.0.0.0 203.0.113.2"]:
        assert needle in edge, f"Edge-Router config missing: {needle!r}"
    pc2 = t.get_pc_network("PC-User2")
    want_gw = "192.168.10.254" if broken else "192.168.10.1"
    assert pc2["gateway"] == want_gw, f"PC-User2 gateway {pc2['gateway']!r} != {want_gw!r}"
    assert t.get_pc_network("PC-Restricted")["ip"] == "192.168.10.200"
    print(f"  verify({'BROKEN' if broken else 'working'}): OK "
          f"({len(t.list_devices())} devices, {len(t.list_links())} links)")


def main() -> int:
    for broken, fname in [(False, "Lab-4-ACL-NAT-Internet-Edge.pkt"),
                          (True, "Lab-4-ACL-NAT-Internet-Edge-BROKEN.pkt")]:
        print(f"building {fname} ...")
        t = build(broken=broken)
        verify(t, broken)
        out = OUT_DIR / fname
        t.save(out)
        print(f"  saved {out} ({out.stat().st_size} bytes)")

    # round-trip check: decode what we just wrote
    from pt_codec import Topology as T2
    probe = T2.open(OUT_DIR / "Lab-4-ACL-NAT-Internet-Edge.pkt")
    assert len(probe.list_devices()) == 7 and len(probe.list_links()) == 6
    assert "overload" in probe.get_running_config("Edge-Router")
    print("round-trip decode: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
