#!/usr/bin/env python3
"""test-put.py — regression for writer transactionality"""

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
LOG_TO_FILE = False  # Set to True to also write test results to test/test-put.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-put.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
SPECS_ROOT = WORK / "specs"
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-put-x-{os.getpid()}"
SF = f".test-put-y-{os.getpid()}"
SPECS_F = SPECS_ROOT / F
SPECS_SF = SPECS_ROOT / SF
SDIR_F = SPECS_F / ".orderspec-state"
SDIR_SF = SPECS_SF / ".orderspec-state"
TARGET = SDIR_F / "mechanisms.tsv"
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
    if SPECS_ROOT.exists():
        shutil.rmtree(SPECS_ROOT, ignore_errors=True)
    SPECS_ROOT.mkdir(parents=True, exist_ok=True)
    SPECS_F.mkdir(parents=True, exist_ok=True)
    SPECS_SF.mkdir(parents=True, exist_ok=True)
    (SPECS_F / "spec.md").write_text("")
    (SPECS_SF / "spec.md").write_text("")
    run_trace("init", F)
    run_trace("init", SF)

def run_trace(*args, input_text=None):
    cmd = [PY, str(TRACE), "-C", str(WORK)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr

def put_mech(feature, data):
    rc, out, err = run_trace("put-mechanisms", feature, input_text=data)
    return rc

# ── Tests ────────────────────────────────────────────────────────────────────

reset_feature()

# 1. valid write — 5 fields each; mechanism may contain spaces
rc = put_mech(F, f"REQ-001{TAB}direct{TAB}TaskService.softDelete unit test{TAB}svc/task.ts{TAB}unit\n"
                f"AC-014{TAB}documented{TAB}ADR-007 audit semantics{TAB}docs/adr.md{TAB}documented\n")
if rc == 0 and TARGET.exists():
    ok("valid rows written")
else:
    no("valid rows written", f"rc={rc} exists?={TARGET.exists()}")

# 2. header written by script
if TARGET.exists() and TARGET.read_text().splitlines()[0] == "#orderspec mechanisms v1":
    ok("script wrote header")
else:
    no("script wrote header", f"first line: {TARGET.read_text().splitlines()[0] if TARGET.exists() else 'N/A'}")

# 3. empty matrix valid
rc = put_mech(F, "")
if rc == 0:
    ok("empty matrix valid")
else:
    no("empty matrix valid", f"rc={rc}")

# 4. re-put replaces (header only => 2 lines)
lines = TARGET.read_text().splitlines()
if len(lines) == 2:
    ok("re-put replaces not appends")
else:
    no("re-put replaces not appends", f"lines={len(lines)} want 2")

# seed known-good 1-row file
put_mech(F, f"REQ-001{TAB}direct{TAB}soft delete unit{TAB}svc/task.ts{TAB}unit\n")
before = TARGET.read_text()

# 5. bad row → rc2, unchanged
rc = put_mech(F, f"REQ-001{TAB}direct{TAB}soft delete unit{TAB}svc/task.ts{TAB}unit\n"
                f"AC-014{TAB}bogus{TAB}audit{TAB}docs/adr.md{TAB}documented\n")
after = TARGET.read_text()
if rc == 2 and before == after:
    ok("bad row rejected, target unchanged")
else:
    no("bad row rejected, target unchanged", f"rc={rc} changed?={'n' if before == after else 'y'}")

# 6. no .tmp leftover
leftover = list(SDIR_F.glob("*.tmp"))
if len(leftover) == 0:
    ok("no tmp leftover")
else:
    no("no tmp leftover", f"found {len(leftover)}")

# 7. spec-ids: 3 fields → writes spec-ids.tsv
rc, out, err = run_trace("put-spec-ids", SF, input_text=f"SC-001{TAB}SC{TAB}Constraints\n")
SID = SDIR_SF / "spec-ids.tsv"
if rc == 0 and SID.exists() and SID.read_text().splitlines()[0] == "#orderspec spec-ids v1":
    ok("put-spec-ids writes spec-ids.tsv with header")
else:
    no("put-spec-ids writes spec-ids.tsv with header", f"rc={rc} exists?={SID.exists()}")

# 8. uninitialized feature → refused
rc = put_mech("__never_inited__", f"REQ-001{TAB}direct{TAB}x{TAB}svc/x.ts{TAB}unit\n")
if rc != 0:
    ok("refuses uninitialized feature")
else:
    no("refuses uninitialized feature", f"rc={rc} (expected non-zero)")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)