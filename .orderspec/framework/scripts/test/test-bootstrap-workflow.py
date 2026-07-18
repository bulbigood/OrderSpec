#!/usr/bin/env python3
"""Regression tests for unified bootstrap phase routing."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).resolve().parents[1] / "bootstrap_workflow.py"
WORK = Path(tempfile.mkdtemp(prefix="orderspec-bootstrap-workflow-"))
passed = failed = 0


def run(*args):
    process = subprocess.run([sys.executable, str(SCRIPT), "-C", str(WORK), *args], text=True, capture_output=True)
    return process.returncode, json.loads(process.stdout)


def check(condition, name, detail=None):
    global passed, failed
    if condition:
        passed += 1; print(f"PASS: {name}")
    else:
        failed += 1; print(f"FAIL: {name} :: {detail}")


shutil.copytree(ROOT / "framework", WORK / ".orderspec/framework")
(WORK / ".orderspec").mkdir(exist_ok=True)
(WORK / ".orderspec/orderspec.json").write_text('{"framework_version":"0.5.0"}\n', encoding="utf-8")

rc, data = run("inspect")
check(rc == 0 and data["mode"] == "init" and data["next_phase"] == "contracts", "missing contracts select Init", data)

rc, data = run("inspect", "--targeted-caller", "order.spec")
check(rc == 64 and data["error"] == "targeted_amend_requires_caller_contract_and_change", "partial targeted envelope rejected", data)

rc, data = run("next", "--mode", "refine", "--completed", "contracts", "--completed", "constitution")
check(rc == 0 and data["next_phase"] == "agents", "next routes ordered top-level phase", data)

rc, data = run("next", "--mode", "refine", "--completed", "agents")
check(rc == 64 and data["error"] == "phases must complete in declared order", "out-of-order phase completion rejected", data)

rc, data = run("next", "--mode", "targeted-amend", "--completed", "contracts", "--completed", "validation")
check(rc == 0 and data["status"] == "ready_to_finalize", "targeted amend uses bounded phase set", data)

shutil.rmtree(WORK, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
