#!/usr/bin/env python3
"""test-extract.py — comprehensive extract-spec + extract-trace + lint regression"""

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
LOG_TO_FILE = False  # Set to True to also write test results to test/test-extract.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-extract.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
SPECS_ROOT = WORK / "specs"
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = "F"
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

def field(path, spec_id, col_idx):
    if not path.exists():
        return "<<MISSING>>"
    for line in path.read_text().splitlines()[2:]:
        parts = line.split(TAB)
        if parts and parts[0] == spec_id:
            if col_idx < len(parts):
                return parts[col_idx]
    return "<<MISSING>>"

# ── extract-spec ─────────────────────────────────────────────────────────────
reset_feature()
(SPECS / "spec.md").write_text("""## 4. Functional Requirements
- **REQ-001**: The Task model MUST include isDeleted.
- **REQ-002**: AuditLog model.
## 14. Edge Cases
- **EDGE-004**: History endpoint queried with a non-existent taskId → covered by AC-011.
## 15. Acceptance Criteria
- **AC-011**: **Given** a non-existent taskId, **Then** empty results.
- **SC-001**: Soft-deleted excluded.
""")
run_trace("extract-spec-ids", F)
out = SDIR / "spec-ids.tsv"

text = out.read_text()
if f"REQ-001{TAB}REQ{TAB}functional" in text:
    ok("spec: REQ-001 extracted")
else:
    bad("spec: REQ-001")

if f"EDGE-004{TAB}EDGE{TAB}edge-cases" in text:
    ok("spec: EDGE-004 extracted")
else:
    bad("spec: EDGE-004")

if f"AC-011{TAB}AC{TAB}acceptance" in text:
    ok("spec: AC-011 extracted")
else:
    bad("spec: AC-011")

if f"SC-001{TAB}SC{TAB}success-criteria" in text:
    ok("spec: SC-001 extracted")
else:
    bad("spec: SC-001")

ac_count = text.count("AC-011")
if ac_count == 1:
    ok("spec: no prose-induced AC-011 dup")
else:
    bad(f"spec: AC-011 duplicated by prose (count={ac_count})")

# lint needs mechanisms.tsv — seed a dummy one
mech = SDIR / "mechanisms.tsv"
mech.write_text(f"#orderspec mechanisms v1\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\n")
rc, _, _ = run_trace("lint", F)
if rc == 0:
    ok("spec-ids.tsv passes lint")
else:
    bad("spec-ids.tsv lint")

# ── extract-trace ────────────────────────────────────────────────────────────
reset_feature()
mech = SDIR / "mechanisms.tsv"
mech.write_text(f"#orderspec mechanisms v1\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\n"
                f"REQ-001{TAB}direct{TAB}Task model{TAB}src/models/task.model.js{TAB}unit\n"
                f"AC-007{TAB}direct{TAB}PATCH 400 on deleted{TAB}tests/integration/task.test.js{TAB}integration\n"
                f"NFR-002{TAB}documented{TAB}append-only{TAB}src/models/auditLog.model.js{TAB}documented\n"
                f"AC-011{TAB}documented{TAB}empty results{TAB}src/services/auditLog.service.js{TAB}documented\n"
                f"EDGE-004{TAB}delegated:AC-011{TAB}history empty{TAB}src/services/auditLog.service.js{TAB}integration\n")
(SPECS / "tasks.md").write_text("""# Tasks
- [ ] T001 [US1] | src/models/task.model.js | REQ-001 | Add fields to Task model
- [ ] T011 [US1] | tests/integration/task.test.js | AC-007 | Integration test PATCH deleted task
- [ ] T012 [US1] | tests/integration/task.test.js | AC-007 | Another test case for deleted task
Some prose mentioning REQ-001 that is NOT a task line.
""")
rc, out_text, err_text = run_trace("extract-trace", F)
if rc != 0:
    print(f"extract-trace stderr: {err_text}", file=sys.stderr)
out = SDIR / "traceability.tsv"

text = out.read_text()
if f"REQ-001{TAB}T001{TAB}src/models/task.model.js{TAB}tasks.md" in text:
    ok("trace: REQ-001 single task")
else:
    bad(f"trace: REQ-001 row :: {field(out, 'REQ-001', 1)}")

if f"AC-007{TAB}T011;T012{TAB}tests/integration/task.test.js{TAB}tasks.md" in text:
    ok("trace: AC-007 aggregated")
else:
    bad(f"trace: AC-007 :: {field(out, 'AC-007', 1)}")

# documented IDs appear in traceability.tsv with source=plan.md and their primary_files
if f"NFR-002{TAB}{TAB}src/models/auditLog.model.js{TAB}plan.md" in text:
    ok("trace: NFR-002 documented→plan.md")
else:
    bad(f"trace: NFR-002 :: {field(out, 'NFR-002', 2)}")

# delegated IDs do NOT appear in traceability.tsv under Variant A
if f"EDGE-004" not in text:
    ok("trace: EDGE-004 delegated absent (Variant A)")
else:
    bad(f"trace: EDGE-004 should not appear as delegated row :: {field(out, 'EDGE-004', 1)}")

rc, _, _ = run_trace("lint", F)
if rc == 0:
    ok("traceability.tsv passes lint")
else:
    bad("traceability.tsv lint")

# ── coverage_kind lint cases ─────────────────────────────────────────────────
mech_hdr = f"#orderspec mechanisms v1\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\n"

reset_feature()
mech = SDIR / "mechanisms.tsv"
mech.write_text(mech_hdr + f"REQ-001{TAB}direct{TAB}x{TAB}src/a.js{TAB}documented\n")
rc, _, _ = run_trace("lint", F)
if rc == 2:
    ok("ck: direct+documented rejected")
else:
    bad("ck: direct+documented")

reset_feature()
mech.write_text(mech_hdr + f"NFR-002{TAB}documented{TAB}x{TAB}src/a.js{TAB}unit\n")
rc, _, _ = run_trace("lint", F)
if rc == 2:
    ok("ck: documented+unit rejected")
else:
    bad("ck: documented+unit")

reset_feature()
mech.write_text(mech_hdr + f"EDGE-004{TAB}delegated:EDGE-004{TAB}x{TAB}src/a.js{TAB}integration\n")
rc, _, _ = run_trace("lint", F)
if rc == 2:
    ok("ck: delegated self-loop rejected")
else:
    bad("ck: self-loop")

reset_feature()
mech.write_text(mech_hdr + f"EDGE-004{TAB}delegated:BOGUS{TAB}x{TAB}src/a.js{TAB}integration\n")
rc, _, _ = run_trace("lint", F)
if rc == 2:
    ok("ck: malformed delegated target rejected")
else:
    bad("ck: bad target")

reset_feature()
mech = SDIR / "mechanisms.tsv"
mech.write_text(mech_hdr + f"EDGE-004{TAB}delegated:AC-011{TAB}x{TAB}src/a.js{TAB}integration\n"
                f"AC-011{TAB}direct{TAB}y{TAB}src/b.js{TAB}unit\n")
rc, out_text, err_text = run_trace("lint", F)
if rc == 0:
    ok("ck: valid delegated passes")
else:
    bad("ck: valid delegated")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)