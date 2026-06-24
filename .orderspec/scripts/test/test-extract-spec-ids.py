#!/usr/bin/env python3
"""test-extract-spec-ids.py — regression for extract-spec-ids"""

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
LOG_TO_FILE = False  # Set to True to also write test results to test/test-extract-spec-ids.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-extract-spec-ids.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
SPECS_ROOT = WORK / "specs"
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-extract-spec-ids-{os.getpid()}"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".orderspec"
SID = SDIR / "spec-ids.tsv"

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

def write_spec(text):
    (SPECS / "spec.md").write_text(text)

def has(spec_id, kind, section):
    if not SID.exists():
        return False
    target = f"{spec_id}\t{kind}\t{section}"
    return target in SID.read_text()

def datacount():
    if not SID.exists():
        return -1
    lines = SID.read_text().splitlines()
    count = 0
    for line in lines[2:]:
        if line.strip():
            count += 1
    return count

# ── Tests ────────────────────────────────────────────────────────────────────

reset_feature()

# 1. valid multi-prefix spec → correct ids+sections
write_spec("""# Spec
## 4. Functional Requirements
- **REQ-001**: System MUST do X
- **REQ-002**: System MUST do Y
## 13. Invariants
- **INV-001**: balance >= 0
## 15. Acceptance
- **AC-001**: **Given** a, **When** b, **Then** c
## 17. Assumptions
- **ASM-001**: reuse existing auth
""")
rc, out, err = run_trace("extract-spec-ids", F)
if rc == 0 and has("REQ-001", "REQ", "functional") and has("REQ-002", "REQ", "functional") \
   and has("INV-001", "INV", "invariants") and has("AC-001", "AC", "acceptance") \
   and has("ASM-001", "ASM", "assumptions"):
    ok("valid multi-prefix extracted with correct sections")
else:
    no("valid multi-prefix extracted", f"rc={rc} rows={datacount()} :: {SID.read_text() if SID.exists() else 'N/A'}")

# 2. prose mention is NOT extracted (phantom guard)
write_spec("""## 4. Functional Requirements
- **REQ-001**: System MUST do X as required, see also REQ-999 elsewhere.
Some prose referencing REQ-888 in the middle of a sentence.
**Covers**: REQ-001, REQ-777
""")
run_trace("extract-spec-ids", F)
if has("REQ-001", "REQ", "functional") and not has("REQ-999", "REQ", "functional") \
   and not has("REQ-888", "REQ", "functional") and not has("REQ-777", "REQ", "functional"):
    ok("prose/Covers mentions not extracted (only anchor defines id)")
else:
    no("phantom guard", SID.read_text())

# 3. form variations do NOT match (strict anchor)
write_spec("""- **REQ-001**: legit anchor
* **REQ-002**: star bullet, not dash
- REQ-003: no bold
- **REQ-4**: one digit
- **REQ-0005**: four digits
  - **REQ-006**: indented
""")
run_trace("extract-spec-ids", F)
got = datacount()
if got == 1 and has("REQ-001", "REQ", "functional"):
    ok("strict anchor rejects form variations (1 of 6 matched)")
else:
    no("strict anchor", f"rows={got} want 1 :: {SID.read_text()}")

# 4. duplicate id in spec.md → rejected, target untouched
write_spec("""- **REQ-001**: first
""")
run_trace("extract-spec-ids", F)
before = SID.read_text() if SID.exists() else ""
write_spec("""- **REQ-001**: first
- **REQ-001**: duplicate same id
""")
rc, out, err = run_trace("extract-spec-ids", F)
after = SID.read_text() if SID.exists() else ""
if rc != 0 and before == after:
    ok("duplicate id rejected, spec-ids.tsv untouched")
else:
    no("duplicate id rejected", f"rc={rc} changed?={'n' if before == after else 'y'}")

# 5. empty/template spec → empty matrix, rc 0
write_spec("""# Spec
Just prose, no anchored ids here.
## 4. Functional Requirements
(to be filled)
""")
rc, out, err = run_trace("extract-spec-ids", F)
got = datacount()
if rc == 0 and got == 0:
    ok("empty spec → valid empty matrix")
else:
    no("empty spec → empty matrix", f"rc={rc} rows={got}")

# 6. kind == prefix cross-check holds for every emitted row
write_spec("""- **NFR-001**: latency budget
- **UJ-001**: a journey
- **Q-001**: open question
""")
rc, out, err = run_trace("extract-spec-ids", F)
if rc == 0 and has("NFR-001", "NFR", "non-functional") and has("UJ-001", "UJ", "user-journeys") \
   and has("Q-001", "Q", "open-questions"):
    ok("UJ/Q/ASM prefixes pass lint (prefix sets in sync)")
else:
    no("prefix sets in sync", f"rc={rc} :: {SID.read_text() if SID.exists() else 'N/A'}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)