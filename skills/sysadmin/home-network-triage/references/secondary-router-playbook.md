# Secondary router behind an ISP router — decision recipe

Context: one ISP line, ISP router (Airtel, 192.168.1.x, does the PPPoE login), one or more personal routers behind it. Goal order: cheapest working config first.

## Configuration options (cheapest first)

1. **AP mode (recommended default)**: cable ISP-LAN → second router LAN port (not WAN), set the second router to Access Point mode (or just disable its DHCP server and give it a static LAN IP in the ISP subnet). All devices land on 192.168.1.x, one NAT, everything sees everything. No admin of ISP router needed.
2. **Router mode with Dynamic-IP WAN**: cable ISP-LAN → second router WAN(blue) port, second router WAN type = Dynamic IP/DHCP. Works, but double NAT: two subnets (192.168.1.x and 192.168.0.x), devices on opposite sides can't see each other directly, stricter game NAT.
3. **ISP bridge mode + PPPoE on own router**: needs the ISP to enable bridge mode on a port (Airtel: email net@airtel.com; techs may claim a static IP or postpaid is required — push back, it isn't). Then own router dials PPPoE directly (credentials in the Airtel app). Cleanest, most effort, only worth it if the ISP router is the bottleneck.

## WAN-mode decision on the second router

- ISP router already logged into Airtel (normal state) → second router WAN = **Dynamic IP**. Setting PPPoE here too is the classic self-inflicted outage: two devices trying to authenticate, second one silently drops.
- ISP port bridged (special request) → second router WAN = PPPoE with the Airtel app credentials. VLAN ID 100 sometimes needed.

## Dead-WAN diagnosis without admin access (verified working flow)

1. Connect to the second router's WiFi (any band that associates).
2. `ping <gw>` — LAN side alive?
3. `ping -I wlo1 8.8.8.8` → 100% loss + `dig @<gw>` refused + `ping -I wlo1 <isp-dns>` dead = uplink dead.
4. UPnP SOAP: SSDP M-SEARCH bound to the WiFi IP → gatedesc.xml (model ID) → POST `/upnp/control/WANIPConn1` GetStatusInfo + GetExternalIPAddress. "Connected" + empty external IP + old uptime = stale; WAN logically down despite the claim.
5. Verdict: cable/port/WAN-mode between the two routers. Physical fixes first (reseat both ends, correct WAN port, power-cycle), admin fix second (Dynamic IP), reset last.

Caveat: steps 1–3 can all pass while the uplink is still dead when the ONT cable lands in a numbered LAN port instead of the WAN port — LAN ping, DNS relay, and the admin page stay healthy while nothing crosses the router, so "healthy LAN, no internet" on a freshly placed router means the WAN-port cable check comes BEFORE any admin-side WAN debugging.

Dual-homed desktop shortcut (bridge-mode topology): the wired host sits on the same L2 as the router, so `ip neigh` from the wired NIC proves the router is up, while `ping -I <wifi-if> 8.8.8.8` failing proves it forwards nothing — that pair is the cable/port verdict without admin access.

## Factory reset (last resort, physical)

Hold reset pinhole 10s while powered. Effects: WiFi SSID/password gone (TP-Link default: ACTFIBERNET-style SSID + sticker password on ISP-bundled units), admin password = sticker value, WAN config gone. After reset: connect to default SSID with sticker password → admin at gateway IP (sticker login, e.g. act@123 on ACT-bundled TP-Links) → set WAN Dynamic IP → re-create SSID/password. If networks flap in/out of scans right after reset, the unit may be unstable (power adapter) — test hold-time with a phone before configuring.

## Admin-UI lockout trap

TP-Link web UI: 5 failed logins ≈ 10-minute lockout. Failed raw-API login attempts trip the SAME lockout and the API returns hangs/empty bodies instead of error text, so each blind attempt burns 10 minutes. Read the sticker password first; ask the user before trying variants; use the browser UI, not scripted logins.

## ISP-bundled TP-Link (EX220 family) — containment facts (verified live)

The ISP SKU (e.g. EX220-G2u, "G2u" = ISP-only channel) is contained in FIRMWARE, not hardware. Verified live on the ACT unit:

- Identify the exact SKU from the login page HTML (no login needed): `curl http://<gw>/` contains `var modelName="EX220-G2u"`. Do not trust the retail-lookup route.
- Port map of the locked unit: 22/tcp dropbear (SSH banner answers, but no shell on stock ISP firmware), 23/tcp telnet open-but-silent, 80/tcp login (passwords RSA-encrypted per request — no credential replay), 1900/tcp UPnP STRIPPED (answers but 404s everything — the SKILL.md SSDP/SOAP status-check flow does NOT work on it), 7547/tcp TR-069 CWMP OPEN. Port 7547 is the ISP's remote-management leash: they can push config/firmware remotely at any time. Any unlock that survives must remove or neuter TR-069 — a soft unlock gets re-locked remotely.
- The lock blocks: unsigned firmware uploads ("Uploaded file not accepted"), hidden features (AP-mode setup dead-ends, USB menu absent), and shell access. It does NOT block using the box as an ordinary gateway for any ISP — the lock is not MAC/carrier binding.
- Only proven full unlock: UART serial header → U-Boot console (bootloader is NOT locked) → TFTP-boot an OpenWrt initramfs → back up ALL 13 MTD partitions → sysupgrade. References: xakcop.com/post/ex220 (full reverse-engineering), github.com/wthw/tapok-ex220 (real ISP-lock liberation log), OpenWrt PR #14001 (EX220 support, flash procedure, web-recovery notes). The web-recovery reset-button mode only accepts signed OEM images — it cannot load OpenWrt.
- MANDATORY before any flash: full MTD backup of all partitions. ISP firmware images are signed and not publicly downloadable — the backup is the only road back to stock.
- Identity resets migrate with the person, not the box: after the ISP swapped the account router and the user re-created their WiFi, the SSID renamed and the old saved NM profile went stale — scan first, then connect by NEW SSID; do not assume the old profile still points at the same box.
- When the user's internet is the agent's own lifeline (CLI session over that line), never leave the desktop's WiFi associated to the router being reconfigured — the reset/reboot blips kill the session. Keep the desktop on the wired path (or a phone hotspot) while probing the router's WiFi, and bind every probe to the right interface.
- Works-with-Airtel answer: connect ONT LAN → router WAN (double NAT, zero calls), or ask Airtel for bridge mode on one ONT port (net@airtel.com) and let the router do PPPoE with VLAN 100. Airtel does not MAC-bind; the second router needs no unlock to carry the connection. With a STATIC public IP plan the cleanest state (achieved here): personal router WAN = Static IP with the public address, ISP-side stays bridged, everything behind the router on 192.168.0.x.
