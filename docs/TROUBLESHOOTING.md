# Troubleshooting walkthrough: "User cannot access external server"

**Scenario.** PC-User2 (192.168.10.11) reports it cannot open
`http://198.51.100.10`. PC-User1 right next to it works fine.

**File.** Open `Lab-4-ACL-NAT-Internet-Edge-BROKEN.pkt` — a fault has been
injected for this exercise. (The fix is at the bottom; try the method first.)

**The method.** A packet from PC-User2 to the web server must survive six
checkpoints. Test them *in order* and stop at the first one that fails —
everything past it is a guess until that layer is healthy.

```
 1. IP?          Does the host have a correct address/mask?
 2. Gateway?     Can it reach its default gateway?
 3. Route?       Does Edge-Router know where the destination is?
 4. NAT?         Is the private address being translated?
 5. ACL?         Is policy permitting the traffic?
 6. Destination? Is the server actually up and listening?
```

---

## 1. IP?

**Where:** the complaining host itself.

**Commands** (PC-User2 → Desktop → Command Prompt):

```
ipconfig
```

**Expect:** `192.168.10.11`, mask `255.255.255.0`.

**Result here:** ✅ correct. The host knows who it is. Move on — and notice
what this step just ruled out: no duplicate IP, no APIPA address, no typo in
the mask. If this had failed, the fix would be in IP Configuration, and
there'd be no reason to touch the router at all.

## 2. Gateway?

**Where:** still the host. The gateway is the *first router hop* — if the
host can't reach it, nothing off-subnet can ever work.

**Commands:**

```
ipconfig          (note the gateway field)
ping 192.168.10.254
```

**Expect:** replies from the gateway.

**Result here:** ❌ **Request timed out.** The gateway doesn't answer.

Stop. This is the layer that's broken — but *why*? Two possibilities:
the gateway address on the PC is wrong, or the router interface is down.
Check the router side before changing anything:

**Where:** Edge-Router CLI:

```
show ip interface brief
```

**Expect:** `GigabitEthernet0/0/0` is `up/up` with `192.168.10.1`.

**Result here:** ✅ the router is fine — its inside interface really is
`.1`. So the PC is pointed at a gateway that doesn't exist (`.254`).

**Root cause found at step 2.** A wrong default gateway: the single most
common "can't reach the internet" ticket in a NOC, and a 30-second fix.

> Methodology note: we did **not** need steps 3–6 to find this. But a good
> habit is to know what each of them *would* look like, so when the fault
> is deeper you don't stall. Read on for the full tour.

## 3. Route?

**Where:** Edge-Router.

**Commands:**

```
show ip route
```

**Expect:** a static default `S* 0.0.0.0/0 via 203.0.113.2`, plus connected
routes for `192.168.10.0/24` and `203.0.113.0/30`.

**Result here:** ✅ healthy. If the default route were missing, LAN hosts
could ping the router but nothing beyond it — symptom looks identical to a
NAT failure, which is why order matters.

## 4. NAT?

**Where:** Edge-Router.

**Commands:**

```
show ip nat statistics
show ip nat translations
```

**Expect:** an entry like

```
icmp 203.0.113.1:1025   192.168.10.11:1025   198.51.100.10:1025  ...
```

— the private address translated to the outside interface address with a
unique port. That's PAT doing its job.

**Result here:** ✅ (once the gateway is fixed, translations appear).
Classic NAT faults to recognize: `ip nat inside` / `ip nat outside` on the
wrong interfaces, or the NAT ACL (`access-list 1`) not matching the LAN
subnet — translations stay empty while routing looks perfect.

## 5. ACL?

**Where:** Edge-Router.

**Commands:**

```
show access-lists 101
show ip interface GigabitEthernet0/0/0 | include access
```

**Expect:** permit counters climbing on the `eq 80`/`eq 443` lines, and the
ACL applied `in` on G0/0/0.

**Result here:** ✅ policy passes web traffic. Two ACL faults worth knowing:
entries in the wrong order (a broad `permit` above a specific `deny`
silently neuters the deny), and the implicit `deny ip any any` at the end
of every ACL — forget your final `permit`, and *everything* not explicitly
allowed dies quietly. `show access-lists` counters are your evidence: a
climbing deny counter next to a failing flow is a conviction.

> Try it: from **PC-Restricted** (192.168.10.200, inside the denied
> `192.168.10.128/25` range), ping the server. It fails — then watch the
> `deny ip 192.168.10.128 0.0.0.127 any` counter increment. That's what a
> guilty ACL looks like.

## 6. Destination?

**Where:** the far end.

**Checks:** on Web-Server → Services tab, HTTP is **ON**; its IP config is
`198.51.100.10/24` with gateway `198.51.100.1`.
From ISP-Router, `ping 198.51.100.10` should succeed — proving the server
segment is healthy independent of NAT/ACL.

**Result here:** ✅ the server was never the problem. Checking it last is
deliberate: most "server is down" escalations are actually steps 1–5.

---

## The fix

On **PC-User2** → Desktop → IP Configuration, set **Default Gateway** to
`192.168.10.1`. Then verify, bottom-up:

```
ping 192.168.10.1        (gateway ✅)
ping 203.0.113.2         (through the router ✅)
ping 198.51.100.10       (end to end ✅)
```

Open `http://198.51.100.10` in the browser. On Edge-Router,
`show ip nat translations` now shows PC-User2's sessions.

## Break it yourself (more reps)

Each fault below produces the *same* user complaint. Predict which step
catches it, inject it, then prove yourself right:

| # | Fault (on Edge-Router unless noted) | Step that catches it |
|---|--------------------------------------|----------------------|
| 1 | `no ip nat inside` on G0/0/0 | 4 — translations stay empty |
| 2 | Change NAT ACL to `access-list 1 permit 192.168.20.0 0.0.0.255` | 4 — LAN no longer matches |
| 3 | Add `access-list 101 deny tcp any any eq 80` at the **top** | 5 — web dies, counter proves it |
| 4 | `shutdown` G0/0/1 | 3 — default route's next-hop unreachable |
| 5 | PC mask `255.255.0.0` instead of `/24` | 1 — subtlest one; think about why |
| 6 | Remove the final `permit ip any any` | 5 — implicit deny kills the flow |

Undo each with `configure terminal` + the inverse command, and re-verify
with the Quick-start checklist in the README.
