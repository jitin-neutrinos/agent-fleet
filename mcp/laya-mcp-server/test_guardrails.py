#!/usr/bin/env python3
"""Self-check: run to verify laya-guardrails hard patterns + gate flow."""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("lg", "/home/notjitin/.hermes/plugins/laya-guardrails/__init__.py")
lg = importlib.util.module_from_spec(spec); spec.loader.exec_module(lg)
assert any(p.search("sudo mkfs.ext4 /dev/sdb1") for p, _ in lg._HARD)
assert not any(p.search("git status") for p, _ in lg._HARD)
assert lg.gate_shell_command("terminal", {"command": "git status"}) is None
assert lg.gate_shell_command("terminal", {"command": "sudo ntfsfix /dev/sda1"})["action"] == "approve"
print("laya-guardrails self-check: PASS")
