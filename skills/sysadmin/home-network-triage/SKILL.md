---
name: home-network-triage
description: Use when a home router, WiFi, or internet line misbehaves.
---
# Home network triage (kurama-core + Jitin's home routers)

The house runs one ISP line (Airtel FTTH). Current mode (verify with `ip route` each session — Airtel reprovisions remotely): the ONT is bridged/direct — the desktop's LAN NIC gets a PUBLIC-range IP (122.166.x.x/22) straight from Airtel's network, and the gateway (122.166.219.1) is Airtel's own equipment with no admin UI on any port. There is no user-configurable router in the path; any LAN device plugged into the ONT gets internet automatically with no setup. Never touch the ONT's config or the line itself; diagnose from this desktop first.

Bridged mode inverts the usual cabling: the desktop NIC itself has NO cable-path visibility to a second router's WAN port. A phone/desktop on the second router's WiFi can only prove the router's LAN side and DNS; the WAN-side verdict comes from the wired host (which sees the other side) plus the user's one physical check — the ONT cable must land in the router's WAN(blue) port, not a numbered LAN port. A LAN-port connection reproduces every dead-WAN symptom while the router looks fully healthy.

## Triage ladder (do in this order)

1. **Radio-level checks first** — before touching NM, check `rfkill list` and `nmcli radio all`. A soft-blocked WiFi radio presents as the network "unavailable" with an empty scan list, and looks exactly like a broken router. `rfkill unblock all` + `nmcli radio wifi on` fixes it. Recheck after reboots — the block can come back.
2. **Identify the addressing mode before assuming subnets**: `nmcli device status` + `ip route` + `nmcli -f DHCP4 dev show <iface>`. Public-range IP on the desktop NIC = bridge/direct mode (current state); 100.64.0.0/10 = CGNAT; RFC1918 = a home router is in the path again. Never assume a "no internet" report means the whole line is down while a working default route exists on a different interface.
3. **Test each path independently** — the desktop can be on LAN (main router) and WiFi (second router) at once:
   - `ping -I <iface> <gateway>` — is the router's LAN side alive?
   - `ping -I <iface> 8.8.8.8` + `curl --interface <iface> https://api.ipify.org` — does THAT path reach the internet?
   - `dig @<router-ip> google.com` — is the router's DNS relay working?
   The control test (path you know works) proves the desktop's own stack is fine before blaming a router.
4. **Ask the router itself via UPnP** — no admin login needed. SSDP multicast only goes out the interface you bind: `socat - UDP4-DATAGRAM:239.255.255.250:1900,bind=<wifi-ip>` with an M-SEARCH payload; then fetch the device description at the Location URL from the SSDP reply (on the Airtel router it is `http://192.168.1.1:5555/DeviceDescription.xml` — do NOT assume `/upnp/control/WANIPConn1`, the controlURL is arbitrary, e.g. `/ctrl?11`) and SOAP-POST `GetExternalIPAddress`/`GetStatusInfo` to the controlURL parsed from that XML. An UPnP WAN status of "Connected" with an EMPTY external IP and an uptime frozen at hours-old = stale state; the WAN link is logically dead. This identifies a dead uplink with zero credentials.
5. **Aim tests at the right hop**: when the second router's LAN side answers ping but traceroute dies at hop 1 and direct pings to the ISP DNS servers it handed out via DHCP also fail, the WAN uplink is dead — the problem is between the two routers (cable/port/WAN mode), not WiFi and not the line.
6. **Second-router WiFi diagnostics from the wired host (dual-homed)**: the desktop routinely keeps a WiFi association to the second router while its wired NIC owns the default route. Bind every probe explicitly: `ping -I wlo1 8.8.8.8` tests the WiFi path's internet, `dig @<router-ip>` tests its DNS relay, `ping -I wlo1 <router>` tests its LAN side. Do NOT read unbound results as WiFi-path verdicts — the wired default route answers them and shows a healthy line that proves nothing about the router.

## Secondary-router verdict table

| Symptom | Cause | Fix |
|---|---|---|
| LAN side fine, WAN no external IP, UPnP state stale | WAN cable loose/wrong port, or WAN mode misconfigured | Reseat cable ISP-LAN → WAN(blue) port; power-cycle; if still dead, admin UI → WAN = Dynamic IP (ISP router already does PPPoE) |
| Two routers, both NAT, some things unreachable | Double NAT (normal-ish, mostly harmless) | Leave it, or bridge/AP mode the second router |
| Second router "bricks" after enabling bridge mode | Subnet/DHCP conflict with ISP router | Factory reset the second router, use AP mode instead of bridge |
| Admin page unreachable | You're not on that router's subnet | Connect to that router's WiFi first; admin URL is its gateway IP (`ip route` while connected) |

## Getting into the admin UI

- Modern TP-Link (EX22x era): `/cgi/getParm` returns a per-request RSA key; login is GET/POST to `/cgi/login?UserName=<rsa(b64(user))>&Passwd=<rsa(b64(pw))>` — but the endpoint hangs with empty responses when the UI's lockout is engaged and does not say so. **Do not hand-roll the crypto API for login attempts: 5 failures trigger a ~10-minute lockout that also blocks the browser UI, and the raw API gives no error text.** Use the real browser UI (browser tools) for logins; reserve raw cgis for unauthenticated reads (getParm, getBusy, UPnP).
- `getBusy` (`var isLogined=...`) is the unauthenticated session-state probe.
- Factory-reset router lands on its default subnet (e.g. 192.168.0.1) while the desktop's wired NIC holds a static IP on a different one: add a throwaway secondary IP on the wired NIC — `sudo ip addr add 192.168.0.23/24 dev enp4s0` — to reach the admin page over the cable, keeping the WiFi free for a lifeline connection. Remove it afterwards with `ip addr del`.
- ISP-bundled TP-Link units (EX220-G2u family): SKU identification from the login-page HTML, the locked port map (TR-069 on 7547 is the ISP leash), and the only proven unlock path (UART/U-Boot → OpenWrt, MTD backup first) live in `references/secondary-router-playbook.md` → "ISP-bundled TP-Link (EX220 family)". Note their UPnP is stripped — the SSDP/SOAP WAN-status flow above does not work on them.
- User is non-technical: physical steps (reseat cable, press reset pinhole 10s while powered, read the sticker) are given as numbered plain-language instructions; everything else stays on the agent.

## NetworkManager on this host — pitfalls

- Connecting to a WPA network by profile: `nmcli con add type wifi con-name X ifname wlo1 ssid "SSID"` then `nmcli con modify X 802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.psk '<pw>'`, then `nmcli con up X`. `nmcli --ask`/`passwd-file` argument placement varies by version — the add+modify+up path is the reliable one.
- "The Wi-Fi network could not be found" on `con up` with the SSID visible in `device wifi list` = the AP is flapping out of scan between list and activation. Retry in a loop: rescan → check list → up. If the SSID appears/disappears across scans, the AP is unstable (fresh factory reset still settling, failing power adapter, or distance) — tell the user to check router lights and test with a phone before burning more attempts.
- Weak 5G signal (<35%) on this desktop's Intel card can fail association outright (auth → assoc → dropped, repeatedly) while 2.4G connects fine — try the 2.4G SSID before concluding credentials are wrong.
- nmcli is fine for WiFi on this Wayland host; the failures to avoid are xdotool/xrandr-style DISPLAY tools, not NM.
- After fixing, leave the desktop dual-homed only deliberately: verify which interface owns the default route (`ip route`) before declaring which network "works".

## Static-IP cutover to a private-subnet router (verified working, this line)

When a formerly bridged/direct line (desktop NIC holds the public static IP itself) gets a personal router with the public IP on its WAN side, the desktop MUST move to DHCP on its wired profile or both sides fight over one address. Order matters — done wrong, the whole internet drops repeatedly and looks like a router fault:

1. Router side first (user in admin UI, plain-language steps): Network → "Internet" IS the WAN menu on TP-Link (not labelled WAN). Connection type Static IP with the public IP/mask/gateway/DNS. LAN = 192.168.0.1/24, DHCP server ON. WiFi security = WPA2-Personal (AES) — NOT the WPA1/WPA2 mixed default: WPA1-mixed makes newer devices (smart TVs especially) refuse or fail to associate, while the same device connects to a clean-WPA2 hotspot, which reads as a "broken TV".
2. Desktop last: `nmcli con modify "Home LAN" ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.dns ""` then `nmcli con up "Home LAN"`. Only after the router holds the public IP.
3. While diagnosing with WiFi joined to the router, set `nmcli con modify <wifiprofile> ipv4.never-default yes ipv6.never-default yes connection.autoconnect no` — otherwise the WiFi default route (higher metric) fights the wired one and the user loses internet every time you touch the WiFi. Revert `autoconnect` at the end if wanted.
- IP CONFLICT signature: the exact same public IP answering on two interfaces with different MACs (`arping -I <iface>` each), or `dhcp_server_identifier` in the WiFi DHCP lease EQUALING the desktop's own static IP — means the router AND the desktop both claim the address; the router is bridging its WAN net onto WiFi. Fix is the cutover above, not more probing.
- After the cutover, `curl https://api.ipify.org` from the desktop should return the SAME public IP as before (the router now NATs it) — that, not the desktop's new 192.168.x address, is the verification the line carried over.
- Do not guess WiFi passwords at a freshly reset router — NM just shows endless "connecting (need authentication)" with supplicant-disconnect reasons, and each wrong try is a blind wait. Ask the user for the current password (they set it during setup) instead of burning 90s nmcli timeouts.
- WiFi channel plan for dense apartments (applied + verified): 2.4 GHz fixed channel 6 (check the live scan first — pick the empty one of 1/6/11), width 20 MHz; 5 GHz fixed channel 149 range (36-48 are the crowded consumer defaults), width 80 MHz. Fixed channels beat Auto in high-density buildings — Auto parks on crowded defaults. TP-Link EX220 exposes one channel dropdown covering 36-161 for 5 GHz; "Interval of auto channel selection" is irrelevant once Channel is fixed. Verify after saving with `nmcli dev wifi list --rescan yes`: SSID + channel + rate column shows the landed channel and the 1170 Mbit/s 5G rate.

## Tailscale on this network (the streaming / remote-access path)

- When a Tailscale-connected stream or remote session between two of Jitin's machines is laggy/jittery, check the PATH first: `tailscale status` showing `relay "<region>"` next to the peer means all traffic goes through a DERP relay server (regional, e.g. blr), NOT a direct connection — `tailscale ping <peer>` confirms with `via DERP(...)` and `direct connection not established`. A relay adds variable latency and caps bandwidth; gigabit LANs at both ends are irrelevant because the traffic crosses the internet through the relay. This check comes BEFORE touching MTU, Sunshine config, or encoder settings.
- Get DIRECT — find the REAL blocker before proposing fixes; the remote firewall is only ONE possibility and on this network it was NOT the culprit:
  1. `tailscale netcheck` on BOTH ends. `UDP: true` + `MappingVariesByDestIP: false` looks healthy but does NOT rule out CGNAT — STUN can see a stable mapping while the outer NAT layer still refuses hole punches.
  2. **CGNAT test (decisive, from the home desktop)**: compare the router's UPnP WAN IP (SOAP `GetExternalIPAddress`, see step 4 above) against `curl https://api.ipify.org`. If they DIFFER, and the router-reported IP falls in 100.64.0.0/10, the ISP line is behind carrier-grade NAT: two NAT layers, and the outer one is ISP-controlled. Cross-check: the desktop's self-advertised IPv4 endpoints in `sudo tailscale debug netmap` change external PORT between runs — unpredictable outer mapping = hard NAT = hole punching cannot succeed from this side.
  3. Hotspot test has a blind spot on Indian ISPs: mobile hotspot data is ALSO CGNAT/hard-NAT, so "direct on hotspot = office firewall" is only valid when the home side is NOT CGNAT. If the home side fails test 2, a DERP-everywhere result is expected regardless of the remote network.
  - If CGNAT is confirmed NOW (re-test each time: this line has also run in direct/bridge mode handing out public IPv4, and Airtel firmware pushes can flip it back), the fixes are (in order): IPv6 direct path first (both Airtel ends get global v6; no NAT on v6; on the client run `tailscale ping <peer>` up to ~20 times — community-verified that the v6 upgrade can take that many probes; zero config, zero risk); then ask Airtel for a public/static IPv4 (support call or ~₹200-300/mo add-on — with a real WAN IP the desktop is directly reachable and every peer connects direct); then a cheap India-region VPS as an own relay/subnet node. Router port-forwarding does NOT help under CGNAT — it opens only the inner layer.
- Remote-safety gate: when the user's ONLY access to this desktop is via Tailscale (they are at the office), do NOT restart tailscaled, change its port (`/etc/default/tailscaled`), or alter tailscale/firewall config on the home side. Run read-only checks only (`status`, `netcheck`, `debug netmap`, `debug portmap`, `tailscale ping`); `tailscale ping` is safe and never drops existing sessions.
- `tailscale0` MTU 1280 is BY DESIGN (Tailscale header overhead) — never "fix" it; real LAN NICs stay at 1500.
- Tailscale binding quirk: services bound to the tailscale IP (e.g. Sunshine `bind_address = <tailscale-ip>`) only appear on that IP in `ss -tlnp`/`ss -ulnp` — grep the tailscale IP, not `0.0.0.0`, or you wrongly conclude the service is down.
## SSH into fleet machines over Tailscale

See `references/ssh-remote-access.md` for the SSH-reachability ladder (sshd vs firewall vs Tailscale), Windows OpenSSH + Entra ID auth limits, and the one-command-per-line rule for PowerShell handoffs.

- iperf3 path testing: install with `dnf5 install iperf3` on this desktop (server: `iperf3 -s -D`); a Windows peer needs iperf3.exe from iperf.fr run as `iperf3.exe -s` with firewall allowance for port 5201 — without it the client times out and that is a setup gap, not a network fault. Jitter/loss test: `iperf3 -c <peer-tailscale-ip> -u -b 20M -t 10 -R`; keep `-t` short so the client finishes inside one terminal call's timeout (a long run gets killed mid-test with only truncated output).

## Finding LAN devices (no nmap/arp-scan on this host)

Sweep with a Python ThreadPoolExecutor firing `ping -c1 -W1` per IP (100+ workers clears a /24 in ~2s; a /22 needs per-segment sweeps), then `ip neigh show dev <iface>` for MACs. Broadcast ping (`ping -b`) populates nothing useful here — skip it. A device absent from a full sweep is unpowered, on a dead cable, or on an ONT port Airtel disabled from the backend — their ONTs are locked and ports are provisioned remotely, only Airtel support can enable one.

Airtel Xstream Play box on LAN: plug-and-play per Airtel's own manual (Ethernet needs zero settings). Invisible in a sweep = power/cable/disabled port, not configuration. TV shows "no signal"/no channels despite box online = account/device registration (Airtel Thanks app → Xstream Box, or call 121), not networking. The box has built-in Wi-Fi as a fallback path.

## Reporting to this user

Plain language, no jargon in chat (analogies like "post office with no delivery truck"); evidence quoted as real command outputs; full technical detail in a scratch file (`~/scratch/<topic>.txt`) with the path given. State physical next-steps for the user explicitly and offer to verify after they act. If a fix needs admin credentials nobody has, say so plainly and lay out the reset path — factory reset wipes WiFi config and restores the sticker-default admin password; warn that it erases the SSID/password and needs re-setup.

When diagnosis ends on a user physical step (cable reseat, reset pinhole, power-cycle), close the message with exactly what was verified working vs not (e.g. "your own internet is unaffected — verified live"), the single numbered physical action, and an explicit "tell me when done — I'll re-test from here immediately". Do not ask the user to run network commands: everything runnable stays on the agent; the user only touches hardware. A stuck diagnosis is NOT an unresolved failure if it terminates in a concrete physical action for the user — report it as such, and re-test with the interface-bound probes above the moment they confirm.
