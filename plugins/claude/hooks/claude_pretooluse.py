#!/usr/bin/env python3
"""Claude Code PreToolUse(Bash) hook -> laya guardrail (hard patterns + risk_gate).

stdin: Claude hook JSON {tool_name, tool_input:{command}, ...}
Exit 0 = allow. Exit 2 + stderr = block (Claude shows stderr to the model).
Never blocks on laya failure (fail-open).
"""
import json, sys, urllib.request

HARD = [
    ("/run/media/notjitin|/media/notjitin|ntfs-3g|mount\\.ntfs|\\bmount\\b[^;|]*\\bntfs", "touches or mounts the Windows/NTFS disks"),
    ("/boot/efi", "touches the EFI boot partition"),
    ("mkfs", "formats a filesystem"),
    ("dd of=/dev/", "raw disk write"),
    ("ntfsfix", "NTFS repair outside Windows"),
    ("ntfsclone", "NTFS clone"),
    ("ntfsresize", "NTFS resize"),
    ("wipefs", "filesystem wipe"),
    ("blkdiscard", "block discard wipe"),
    ("shred ", "secure-wipe command"),
]
import re
DMF = re.compile(r"\bdnf(\d+)?\s+(remove|erase|autoremove)\b[^;|]*\b(kernel|nvidia|mesa)\b", re.I)
DUP = re.compile(r"\bdnf(\d+)?\s+(upgrade|distro-sync|update)\b", re.I)
NV = re.compile(r"\b(nvidia|mesa|proton|wine|ffmpeg)\b[^;|]*\b(install|download|curl|wget)\b|\b(curl|wget)\b[^;|]*\b(nvidia|mesa)\b", re.I)
RMRF = re.compile(r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+/(?!home/notjitin/Work/scratch|tmp|var/tmp)")
RAWDEV = re.compile(r">\s*/dev/(sd|nvme|hd|vd)[a-z]")
SAFE_ALLOW_PREFIXES = ("git status", "git diff", "git log", "ls", "cat", "head", "tail", "grep", "rg", "pwd", "which")

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") not in ("Bash", "bash"):
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if not cmd.strip():
        return 0
    low = cmd.lower()
    reasons = []
    for pat, reason in HARD:
        if pat in low:
            reasons.append(reason)
    if DMF.search(cmd): reasons.append("removes kernel/driver packages")
    if DUP.search(cmd): reasons.append("system update outside nobara-sync")
    if NV.search(cmd): reasons.append("hand-installs Nobara-managed components")
    if RMRF.search(cmd): reasons.append("recursive delete outside scratch/tmp")
    if RAWDEV.search(cmd): reasons.append("overwrites a raw block device")
    if reasons:
        print("BLOCKED by laya guardrail: this command " + "; ".join(reasons) +
              ". Ask the user for explicit confirmation before retrying.", file=sys.stderr)
        return 2
    stripped = cmd.strip().lower()
    if any(stripped.startswith(p) for p in SAFE_ALLOW_PREFIXES):
        return 0
    # Designated throwaway workspaces (scratch/cache): sandboxed by machine
    # policy, nothing here is system state — skip Laya confirmation scoring.
    # Hard patterns above still apply everywhere.
    cwd = payload.get("cwd", "")
    if cwd.startswith(("/home/notjitin/.hermes/cache/", "/home/notjitin/Work/scratch/", "/tmp/")):
        return 0
    try:
        body = json.dumps({"state": {"action": cmd[:6000]}, "questions": {
            "destructive": {"type": "noul", "instructions": "Would running this damage, wipe, or irreversibly change the operating system, disks, boot setup, or important data?"},
            "in_scope": {"type": "noul", "instructions": "Is this action clearly in service of routine development or system administration the user asked for?"}}}).encode()
        req = urllib.request.Request("http://127.0.0.1:8015/v1/systemone", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            answers = json.load(resp).get("answers", {})
        destructive = float(answers.get("destructive", {}).get("noul", 0.0))
        in_scope = float(answers.get("in_scope", {}).get("noul", 1.0))
        risk = min(1.0, destructive + max(0.0, 1.0 - in_scope) * 0.25)
        if risk >= 0.70:
            print(f"BLOCKED by laya guardrail (risk {risk:.2f}): potentially destructive. "
                  f"Command: {cmd[:200]}. Ask the user for explicit confirmation before retrying.", file=sys.stderr)
            return 2
    except Exception:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
