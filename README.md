# Lab 4: ACL + NAT + Internet Edge

An enterprise-style internet edge built in Cisco Packet Tracer: a private LAN
behind **PAT (NAT overload)** and an **extended ACL** enforcing an egress
policy, with a simulated ISP and internet. Includes a deliberately broken
variant so you can practice structured troubleshooting the way a NOC does it.

> **Résumé line:** *Designed and troubleshot an enterprise internet edge in
> Cisco Packet Tracer — PAT/NAT overload, extended ACL egress policy, and a
> repeatable 6-step fault-isolation methodology.*

**Lab series:** [Lab 1](https://github.com/kn2702-sys/enterprise-vlan-lab) · [Lab 2](https://github.com/kn2702-sys/dhcp-dns-failure-lab) · [Lab 3](https://github.com/kn2702-sys/LAB-3-Multi-Router-OSPF-Network) · **Lab 4** · [Lab 5](https://github.com/kn2702-sys/LAB-5-Site-to-Site-VPN-Firewall) · [Lab 6](https://github.com/kn2702-sys/LAB-6-Wireshark-NOC-Troubleshooting) · [Lab 7](https://github.com/kn2702-sys/LAB-7-NOC-Incident-Simulation) · [Lab 8](https://github.com/kn2702-sys/LAB-8-AWS-VPC-Networking)

## Skills demonstrated

- NAT overload (PAT) for internet access from RFC 1918 space
- Extended ACL design: ordered allow/deny entries, `eq` port matching,
  subnet-based deny, applied inbound on the inside interface
- Default routing toward an ISP; why the ISP needs no return route when NAT
  is in play
- Reading `show ip nat translations` / `show access-lists` counters as
  evidence, not guesses
- Structured troubleshooting: **IP → Gateway → Route → NAT → ACL →
  Destination**

## Topology

```
                       192.168.10.0/24  (inside / LAN)
   .10               .11               .200
 PC-User1          PC-User2        PC-Restricted ── denied by ACL 101
   | Fa0/1           | Fa0/2           | Fa0/3
   +-----------------+-----------------+
                     | Fa0/24
                [LAN-Switch]  (2960)
                     | G0/0/0  192.168.10.1
               [Edge-Router]  (ISR 4331)  <-- PAT overload + ACL 101
                     | G0/0/1  203.0.113.1
                     | 203.0.113.0/30  (public-side simulation)
                     | G0/0/0  203.0.113.2
               [ISP-Router]   (ISR 4331)
                     | G0/0/1  198.51.100.1
                     | 198.51.100.0/24  (simulated internet)
                     |
               [Web-Server]  198.51.100.10  (HTTP/HTTPS)
```

## Addressing

| Device        | Interface | IP address    | Mask / Prefix | Gateway      |
|---------------|-----------|---------------|---------------|--------------|
| Edge-Router   | G0/0/0    | 192.168.10.1  | 255.255.255.0 | —            |
| Edge-Router   | G0/0/1    | 203.0.113.1   | 255.255.255.252 | —          |
| ISP-Router    | G0/0/0    | 203.0.113.2   | 255.255.255.252 | —          |
| ISP-Router    | G0/0/1    | 198.51.100.1  | 255.255.255.0 | —            |
| LAN-Switch    | —         | (L2 only)     | —             | —            |
| PC-User1      | Fa0       | 192.168.10.10 | 255.255.255.0 | 192.168.10.1 |
| PC-User2      | Fa0       | 192.168.10.11 | 255.255.255.0 | 192.168.10.1 |
| PC-Restricted | Fa0       | 192.168.10.200| 255.255.255.0 | 192.168.10.1 |
| Web-Server    | Fa0       | 198.51.100.10 | 255.255.255.0 | 198.51.100.1 |

## What's configured

**NAT overload (PAT)** on Edge-Router — one public address serves the whole
LAN:

```
access-list 1 permit 192.168.10.0 0.0.0.255
ip nat inside source list 1 interface GigabitEthernet0/0/1 overload
```

**Extended ACL 101** (inbound on the inside interface) — the egress policy,
in order:

| Order | Entry | Intent |
|-------|-------|--------|
| 1–2 | `permit tcp 192.168.10.0 0.0.0.255 any eq 80` / `eq 443` | Allow HTTP/HTTPS |
| 3–4 | `permit udp ... any eq 53`, `permit icmp ... any` | Allow DNS + ping (ops) |
| 5 | `deny tcp any any eq 23` | **Deny Telnet** everywhere |
| 6 | `deny ip 192.168.10.128 0.0.0.127 any` | **Deny a whole subnet** (PC-Restricted lives here) |
| 7 | `permit ip any any` | Permit remaining required traffic |

Order matters: the denies sit *before* the final permit. Return traffic is
unaffected — it enters via the outside interface, which has no ACL.

**Default route** `0.0.0.0/0 → 203.0.113.2` on Edge-Router. The ISP router
intentionally has **no** route back to `192.168.10.0/24` — with NAT overload
in place it never sees a private address, just like a real ISP.

## Repository contents

```
Lab-4-ACL-NAT-Internet-Edge.pkt          # working lab — open in Packet Tracer
Lab-4-ACL-NAT-Internet-Edge-BROKEN.pkt    # fault injected (see docs/TROUBLESHOOTING.md)
configs/
  edge-router.txt                         # paste-ready CLI (Edge-Router)
  isp-router.txt                          # paste-ready CLI (ISP-Router)
  lan-switch.txt                          # paste-ready CLI (LAN-Switch)
docs/
  TROUBLESHOOTING.md                      # the 6-step method, worked end-to-end
scripts/
  build_topology.py                       # regenerates both .pkt files
```

## Quick start (5 minutes)

1. Open `Lab-4-ACL-NAT-Internet-Edge.pkt` in Cisco Packet Tracer (8.2.1+).
2. Wait for links to converge (green), then on **PC-User1** → Desktop →
   Web Browser → `http://198.51.100.10`. The page loads: NAT + ACL are
   passing web traffic.
3. On **Edge-Router** CLI: `show ip nat translations` — you'll see
   `192.168.10.10` translated to `203.0.113.1` with a unique source port.
   That is PAT.
4. `show access-lists 101` — watch the match counters climb on the
   permit lines.
5. Policy checks:
   - From PC-User1: `telnet 198.51.100.10` → fails (ACL line 5).
   - From **PC-Restricted**: `ping 198.51.100.10` → fails (ACL line 6).
     `show access-lists 101` shows the deny counter incrementing — evidence.

## The troubleshooting method

When "user cannot access external server", work the path in order and stop
at the first layer that fails:

```
IP? → Gateway? → Route? → NAT? → ACL? → Destination?
```

A full worked example — including the deliberately broken `.pkt` in this
repo — is in **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**.

## Build it yourself in Packet Tracer

Prefer the GUI? The `.pkt` is fully reproducible by hand:

1. Place: 2× ISR 4331, 1× 2960 switch, 3× PC-PT, 1× Server-PT.
2. Cable exactly as the topology diagram above (copper straight-through;
   crossover between the two routers).
3. Paste `configs/edge-router.txt`, `configs/isp-router.txt`,
   `configs/lan-switch.txt` into each device's CLI.
4. Set the PC/server IPs from the addressing table (Desktop → IP
   Configuration).
5. On the server: Services tab → HTTP **ON** (default).
6. Run the Quick-start verification above.

## Regenerating the `.pkt` files

The topologies were generated programmatically with the open-source
[`pt_codec`](https://github.com/w4lven/claude-to-packet-tracer) library
(Packet Tracer `.pkt` = encrypted + compressed XML; the library handles the
codec). To rebuild:

```bash
git clone https://github.com/w4lven/claude-to-packet-tracer /tmp/ctt
python3 -m venv /tmp/ctt/.venv && /tmp/ctt/.venv/bin/pip install -r /tmp/ctt/requirements.txt
/tmp/ctt/.venv/bin/python scripts/build_topology.py
```

## Requirements

- Cisco Packet Tracer 8.2.1 or newer (the `.pkt` was encoded for 8.2.1;
  newer releases open it, older ones may not).
- No login or external files needed — everything is in this repo.

## Talking about this in interviews

- "I used PAT so 254 private hosts share one public IP, and verified with
  `show ip nat translations`."
- "The ACL is ordered deliberately — business traffic first, explicit
  denies, then a final permit. I proved the Telnet deny with a failed
  connection *and* the ACL match counter."
- "The ISP has no return route because NAT hides RFC 1918 space — that's
  the design working, not a missing route."
- "When a user couldn't reach the server, I isolated it with IP → Gateway
  → Route → NAT → ACL → Destination instead of guessing."
