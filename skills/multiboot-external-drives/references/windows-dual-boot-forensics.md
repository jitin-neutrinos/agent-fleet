# Windows side of the internal dual-boot: offline forensics & repair from Linux

Session-proven on kurama-core 2026-09-06: Windows 11 partition (nvme0n1p3) examined and
repaired entirely from Nobara while Windows was unbootable (black screen, no display).

## Mounting the Windows partition safely

```bash
sudo mkdir -p /mnt/win-ro
sudo mount -t ntfs3 -o ro,force /dev/nvme0n1p3 /mnt/win-ro   # ro FIRST, always
```

- `force` is needed because a Fast-Startup shutdown leaves the volume dirty.
- Never mount rw while `hiberfil.sys` is fresh: hiberboot resumes the kernel from it and
  will replay the OLD registry state over any offline hive edits. If you must edit hives,
  plan to also set `HiberbootEnabled=0` (below) so the next boot is a true cold boot.

## Reading registry hives offline (regipy)

```bash
python3 -m pip install --user regipy
```

Hives: `/Windows/System32/config/{SYSTEM,SOFTWARE,SAM}`. regipy API gotchas:
- Use `key.iter_values()` / `key.iter_subkeys()` - `.values`/`.subkeys` attributes do NOT exist.
- Hive paths need a LEADING backslash: `RegistryHive(p).get_key(r'\ControlSet001\...')`.
- Find current ControlSet via `\Select` -> `Current` value -> `ControlSet00N`.

High-value keys (all verified on this box):

| What | Path (CCS = ControlSet001) |
|---|---|
| Fast Startup flag | `CCS\Control\Session Manager\Power\HiberbootEnabled` (1=on) |
| Saved display topologies | `CCS\Control\GraphicsDrivers\Configuration` and `\Connectivity` - subkey names encode monitor pairs; a `MTT1337...^` name alone = virtual display as ONLY display (black-screen smoking gun) |
| Device disabled flag | `CCS\Enum\...\<instance>\ConfigFlags` (bit 0x1 = disabled; mirrored in `CCS\Control\Class\{4d36e968...}\NNNN`) |
| Autologin | `SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon` -> `AutoAdminLogon`, `DefaultUserName` |
| Service start type | `CCS\Services\<name>\Start` (2=auto, 3=demand, 4=disabled) |
| Firewall rules | `CCS\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules` - pipe-delimited strings; `RA4=100.64.0.0/255.192.0.0` = tailnet-scoped |
| Boot options | `CCS\Control\SystemStartOptions` (NOEXECUTE, FVEBOOT=nnn means BitLocker recovery ran at boot, NOVGA) |

## Editing hives offline (chntpw/reged)

```bash
sudo dnf5 install chntpw     # provides reged for scripted hive edits
```

Critical rule: registry edits alone do NOT survive a hiberboot resume - the saved kernel
image replays old state on top. Pair any SYSTEM-hive edit with `HiberbootEnabled=0` so the
next boot is a true cold boot.

## Event logs offline (python-evtx)

```bash
python3 -m pip install --user python-evtx
# import is 'from Evtx.Evtx import Evtx' - capital E, NOT 'import evtx'
```
Filter `Windows/System32/winevt/Logs/System.evtx` for EventIDs: 41/6008 (unexpected
shutdown - counts the user's hard power-offs), 6005/6006 (boot / clean shutdown), 7045
(service installs), 4101 (display driver reset). Correlate `hiberfil.sys` mtime with the
last 6006 to prove a Fast-Startup shutdown happened.

## The failure class: virtual display driver strands the host

MTT/IddSampleDriver-style VDDs (Sunshine-VDM scripts, VirtualDisplayDriver) save Windows
display topologies that can end up VDD-as-only-display. Documented failure mode in
VirtualDrivers/Virtual-Display-Driver README: "black screen or display priority gets
scrambled" - their documented recovery is Safe Mode then uninstall VDD. Offline equivalent
from Linux: set the VDD device's `ConfigFlags=1` (disabled) under
`CCS\Enum\ROOT\DISPLAY\NNNN` and delete the poisoned
`GraphicsDrivers\Configuration` / `\Connectivity` subkeys (they are caches - Windows
rebuilds them on next boot).

Aggravator on this box: Sunshine's `global_prep_cmd` runs elevated and FAILED with
`Permission denied` (log: `Program Files/Sunshine/config/sunshine.log`), so the VDM setup
script never ran while a stale VDD-primary topology persisted.

## Sunshine/Moonlight dual-boot specifics (Windows host)

- Config: `C:\Program Files\Sunshine\config\sunshine.conf` (MSI install); global_prep_cmd
  drives `C:\Sunshine-VDM\setup_sunvdm.ps1` / `teardown_sunvdm.ps1`.
- `AutoAdminLogon=0` means no session at boot, so Sunshine has nothing to serve, so
  Moonlight lockout even when the network is fine. Tailscale state
  (`C:\ProgramData\Tailscale\server-state.conf`, base64 profile fields: Hostname,
  WantRunning, RunSSH) was healthy the whole time - check it before blaming the network.
- sshd auto-start + tailnet-scoped firewall rule is NOT a recovery channel until an
  authorized_keys file exists. Admin accounts read from
  `C:\ProgramData\ssh\administrators_authorized_keys` (ACL: Administrators+SYSTEM only) -
  `%USERPROFILE%\.ssh\authorized_keys` is ignored for them unless `AuthorizedKeysFile`
  is overridden. Default sshd_config ships `AuthorizedKeysFile .ssh/authorized_keys`.
- Sunshine's installer firewall rules already cover TCP+UDP; scope new ones with
  `RA4=100.64.0.0/255.192.0.0` (CGNAT = tailnet only).

## Moonlight-cannot-connect triage order (Windows host over Tailscale)

In this order - each step localizes the fault to one layer (verified 2026-09-06):
1. `tailscale status` on BOTH ends - peer listed and online? `tailscale ping <peer>` -
   `pong via <ip>` = direct path fine; if this works, the network is NOT the problem.
2. `https://<host-tsip>:47990` from the client - loads = TCP path fine, fault is UDP.
3. Pairing succeeds but stream fails = UDP 47998/47999/48000 inbound blocked.
4. Web UI dead too = firewall profile problem: Tailscale adapter often lands in the
   Windows "Public" profile where installer rules don't apply. Fix:
   `Set-NetConnectionProfile -InterfaceAlias "Tailscale" -NetworkCategory Private`.
5. Sunshine log shows prep-cmd `Permission denied` + `failed to get display name` x5 =
   the VDD-strands-host failure class above, not a network fault.

Key insight from the live case: tailnet, Sunshine firewall rules, sshd auto-start and
Tailscale auto-auth were ALL already correct - the lockout was one poisoned display
topology plus no authorized_keys. Check the display path before re-doing network config.

## Host-sudo workflow note

The agent safety guard blocks `echo pw | sudo -S` shell patterns. Supported path: put
`SUDO_PASSWORD=...` in `~/.hermes/.env` - the terminal tool auto-rewrites bare `sudo` into
`sudo -S` with the configured password. Writing the line mid-session may not take effect
until the backend reloads env; verify with a cheap `sudo true` before planning around it.

CAUTION (learned the hard way 2026-09-06): the auto-rewrite only fires on a BARE `sudo <cmd>`
in the command string. Redirection and heredoc forms bypass or corrupt it:
- `sudo tee file <<< "$x"` - the heredoc eats the password stdin: "sudo: no password was provided".
- `sudo -S` typed literally triggers the safety block.
- Any command CONTAINING the literal text `sudo -S` (even inside a grep search pattern) can
  trip the block.

Working pattern for root-owned writes: write the file to /tmp as the user first, then
`sudo cp /tmp/file /target`. Multiple `sudo cp` calls are cheap; one blocked call wastes
a round trip.

## reged limits, and python-hivex for deletes

reged `rdel <full key name>` silently fails on names longer than ~79 chars (truncated,
reports "not found"). Display topology names are 80-100+ chars, so topology deletes need
python-hivex:

```bash
sudo dnf5 install python3-hivex   # imports as 'hivex', system python only
python3 - <<'EOF'
import hivex
h = hivex.Hivex('/tmp/SYSTEM.work', write=True)
# walk to the parent node, then:
for c in list(h.node_children(parent)):
    if 'MTT1337' in h.node_name(c):
        h.node_delete_child(c)   # NOTE: takes the CHILD node, not (parent, child)
h.commit(None)
EOF
```

hivex API quirks:
- `node_delete_child(node)` deletes the node passed in (the child), NOT (parent, child).
- `node_set_value(node, val)` wants a dict with key `"t"` (not "type"):
  `{"key": "ConfigFlags", "t": 4, "value": (1).to_bytes(4, "little")}`.
- Read back with `node_get_value` + `value_dword` / `value_string`.

reged `ed <value>` reads the new value from the NEXT stdin line - pipe it as a separate
line (`printf '...\ned HiberbootEnabled\n0\nq\ny\n' | reged -e hive`). Verify every edit
afterward with `hex <value>` against the INSTALLED hive, not the working copy.

## Rescue-session structure (proven end-to-end 2026-09-06)

1. Read-only mount, full forensics pass (hives + evtx + logs) BEFORE any write.
2. Write findings to a forensics.md; present the root-cause chain; get explicit user OK.
3. Back up hives + configs to TWO locations with SHA256SUMS; verify with `sha256sum -c`.
4. Remount rw (`ntfs3 -o force` - hiberboot leaves the dirty bit set); do hive edits on a
   /tmp working copy, verify, then `sudo cp` into place.
5. Re-verify every edit against the INSTALLED hive; sync; unmount.
6. Write CHANGES-APPLIED.md: what changed, what was deliberately NOT changed and why
   (e.g. autologon skipped - MS-account password unknown, never store a guessed password),
   and the in-Windows follow-ups (netplwiz autologin, icacls ACL fix if key auth rejected).
