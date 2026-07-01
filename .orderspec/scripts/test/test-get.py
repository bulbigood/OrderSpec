#!/usr/bin/env python3
"""test-get.py — regression for get command"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
TRACE = SCRIPT_DIR.parent / "traceability.py"

if not TRACE.exists():
    print(f"FATAL: traceability.py not found at {TRACE}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────
LOG_TO_FILE = False  # Set to True to also write test results to test/test-get.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-get.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
sys.path.insert(0, str(SCRIPT_DIR.parent))
from common import FEATURES_DIR
SPECS_ROOT = WORK / FEATURES_DIR
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-get-{os.getpid()}"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".orderspec-state"
TAB = "\t"

pass_count = 0
fail_count = 0

def ok(name):
    global pass_count
    pass_count += 1
    msg = f"PASS: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def no(name, detail=""):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name} :: {detail}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

def reset_feature():
    if SPECS.exists():
        shutil.rmtree(SPECS, ignore_errors=True)
    SPECS.mkdir(parents=True, exist_ok=True)
    (SPECS / "spec.md").write_text("")
    run_trace("init", F)

def run_trace(*args, input_text=None):
    cmd = [PY, str(TRACE), "-C", str(WORK)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr

def put_mech(data):
    rc, out, err = run_trace("put-mechanisms", F, input_text=data)
    return rc

def run_get(*args):
    rc, out, err = run_trace("get", F, *args)
    return rc, out, err

# ── Tests ────────────────────────────────────────────────────────────────────

reset_feature()

# 1. get mechanisms → body only (marker + colnames stripped)
put_mech(f"REQ-001{TAB}direct{TAB}validate email{TAB}src/a.js{TAB}unit\n")
rc, out, err = run_get("mechanisms")
lines = out.strip().splitlines()
if rc == 0 and "REQ-001" in out and "orderspec" not in out and "spec_id" not in out and len(lines) == 1:
    ok("get mechanisms → body only, header stripped")
else:
    no("get mechanisms body", f"rc={rc} out=<{out}>")

# 2. unknown which → exit (64), empty stdout
rc, out, err = run_get("bogus")
if rc != 0 and out == "":
    ok("unknown which → nonzero, empty stdout")
else:
    no("unknown which", f"rc={rc} out=<{out}>")

# 3. missing file → exit 2, empty stdout
rc, out, err = run_get("spec-ids")
if rc != 0 and out == "":
    ok("missing file → nonzero, empty stdout")
else:
    no("missing file", f"rc={rc} out=<{out}>")

# 4. corrupt marker → exit 2, body NOT leaked
mech_path = SDIR / "mechanisms.tsv"
mech_path.write_text(f"garbage marker\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\nREQ-009{TAB}direct{TAB}x{TAB}src/x.js{TAB}unit\n")
rc, out, err = run_get("mechanisms")
if rc == 2 and "REQ-009" not in out:
    ok("corrupt marker → exit 2, body not leaked")
else:
    no("corrupt marker", f"rc={rc} out=<{out}>")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)