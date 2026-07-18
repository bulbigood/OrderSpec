#!/usr/bin/env python3
"""Regression tests for upstream gate report lifecycle handling."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "upstream_gate.py"


def run_guard(report_text, force=False):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / "spec.md"
        report = root / "spec-report.md"
        artifact.write_text("# Spec\n", encoding="utf-8")
        report.write_text(report_text, encoding="utf-8")
        command = [
            sys.executable, str(SCRIPT),
            "--report", str(report),
            "--artifact", str(artifact),
            "--upstream-name", "spec.md",
            "--this", "/order.plan",
            "--build", "/order.spec",
            "--fix", "/order.spec",
            "--recheck", "/order.spec-check",
        ]
        if force:
            command.append("--force")
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


rc, data = run_guard(
    "<!-- orderspec-report-state: CONSUMED_STALE -->\n"
    "# CONSUMED_STALE — spec-report.md\n"
)
expect(rc == 0, f"consumed report blocked: rc={rc} data={data}")
expect(data.get("status") == "advisory", f"wrong consumed status: {data}")
expect(data.get("state") == "consumed_stale", f"missing consumed state: {data}")
expect(data.get("block") is False, f"consumed report marked blocking: {data}")

rc, data = run_guard("# CONSUMED_STALE — spec-report.md\n\nThis is not a PASS verdict.\n")
expect(rc == 0, f"legacy consumed report blocked: rc={rc} data={data}")
expect(data.get("state") == "consumed_stale", f"legacy consumed state missing: {data}")

rc, data = run_guard("# malformed report without verdict\n")
expect(rc == 1, f"malformed report did not fail closed: rc={rc} data={data}")
expect(data.get("verdict") == "unparseable", f"wrong malformed verdict: {data}")

rc, data = run_guard("**Verdict**: BLOCK\n")
expect(rc == 1 and data.get("status") == "halt", f"BLOCK did not halt: rc={rc} data={data}")

rc, data = run_guard("**Verdict**: BLOCK\n", force=True)
expect(rc == 0 and data.get("status") == "forced", f"forced BLOCK failed: rc={rc} data={data}")

rc, data = run_guard("**Verdict**: PASS\n")
expect(rc == 0 and data.get("status") == "ok", f"PASS failed: rc={rc} data={data}")

print("OK: upstream gate distinguishes consumed, malformed, BLOCK, and PASS reports")
