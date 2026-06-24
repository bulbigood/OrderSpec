#!/usr/bin/env python3
"""test-lint.py — regression for lint engine"""

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
LOG_TO_FILE = False  # Set to True to also write test results to test/test-lint.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-lint.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
SPECS_ROOT = WORK / "specs"
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = "F"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".orderspec"
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

def bad(name):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
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

def run_lint():
    rc, out, err = run_trace("lint", F)
    return rc, out + err

def mech_hdr():
    return f"#orderspec mechanisms v1\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\n"

def trace_hdr():
    return f"#orderspec traceability v1\nspec_id{TAB}task_ids{TAB}files{TAB}source\n"

def put_mech(content):
    path = SDIR / "mechanisms.tsv"
    path.write_text(content)

def put_trace(content):
    path = SDIR / "traceability.tsv"
    path.write_text(content)

def assert_rc(expected, name):
    rc, out = run_lint()
    if rc == expected:
        ok(name)
    else:
        bad(f"{name} (rc={rc} want {expected}) :: {out}")

# ── Tests ────────────────────────────────────────────────────────────────────

# 1. happy path
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}Task model adds fields{TAB}src/models/task.model.js{TAB}unit\n")
assert_rc(0, "valid mechanisms.tsv passes")

# 2. documented + multi-path
reset_feature()
put_mech(mech_hdr() + f"NFR-002{TAB}documented{TAB}append only{TAB}src/m/a.js;src/r/v1/t.js{TAB}documented\n")
assert_rc(0, "documented + multi-path passes")

# 3. wrong marker version
reset_feature()
put_mech(f"#orderspec mechanisms v2\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\nREQ-001{TAB}direct{TAB}x{TAB}a.js{TAB}unit\n")
assert_rc(2, "wrong marker version rejected")

# 4. wrong column-names row
reset_feature()
put_mech(f"#orderspec mechanisms v1\nspec_id{TAB}cov{TAB}mechanism{TAB}primary_files{TAB}test_type\nREQ-001{TAB}direct{TAB}x{TAB}a.js{TAB}unit\n")
assert_rc(2, "wrong column names rejected")

# 5. missing column-names row
reset_feature()
put_mech("#orderspec mechanisms v1\n")
assert_rc(2, "missing column-names row rejected")

# 6. em-dash test_type (— is U+2014)
reset_feature()
put_mech(mech_hdr() + f"NFR-002{TAB}documented{TAB}append only{TAB}src/x.js{TAB}\u2014\n")
assert_rc(2, "em-dash test_type rejected")

# 7. duplicate spec_id
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\nREQ-001{TAB}direct{TAB}b{TAB}src/b.js{TAB}unit\n")
assert_rc(2, "duplicate spec_id rejected")

# 8. too few columns
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js\n")
assert_rc(2, "too few columns rejected")

# 9. empty mechanism
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}{TAB}src/a.js{TAB}unit\n")
assert_rc(2, "empty mechanism rejected")

# 10. path with space
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a b.js{TAB}unit\n")
assert_rc(2, "path with space rejected")

# 11. CRLF data row
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\r\n")
assert_rc(2, "CRLF data row rejected")

# 12. malformed spec_id
reset_feature()
put_mech(mech_hdr() + f"REQ-1{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
assert_rc(2, "malformed spec_id rejected")

# 13. blank data line
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n\nREQ-002{TAB}direct{TAB}b{TAB}src/b.js{TAB}unit\n")
assert_rc(2, "blank data line rejected")

# 14. wrong .schema version
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
schema = SDIR / ".schema"
schema.write_text("v9\n")
assert_rc(2, "wrong .schema version rejected")

# 15. valid traceability.tsv
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
put_trace(trace_hdr() + f"REQ-001{TAB}T001{TAB}src/a.js{TAB}tasks.md\n")
assert_rc(0, "valid traceability.tsv passes")

# 16. empty task_ids + source=tasks.md → inconsistent
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
put_trace(trace_hdr() + f"REQ-001{TAB}{TAB}src/a.js{TAB}tasks.md\n")
assert_rc(2, "empty task_ids with source=tasks.md rejected")

# 17. empty task_ids + source=plan.md → OK
reset_feature()
put_mech(mech_hdr() + f"NFR-002{TAB}documented{TAB}append only{TAB}src/a.js{TAB}documented\n")
put_trace(trace_hdr() + f"NFR-002{TAB}{TAB}src/a.js{TAB}plan.md\n")
assert_rc(0, "empty task_ids with source=plan.md passes")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)