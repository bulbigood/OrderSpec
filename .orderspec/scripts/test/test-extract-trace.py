#!/usr/bin/env python3
"""test-extract-trace.py — regression for extract-trace"""

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
LOG_TO_FILE = False  # Set to True to also write test results to test/test-extract-trace.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-extract-trace.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
SPECS_ROOT = WORK / "specs"
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-extract-trace-{os.getpid()}"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".orderspec"
TT = SDIR / "traceability.tsv"
MT = SDIR / "mechanisms.tsv"
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

def write_tasks(text):
    (SPECS / "tasks.md").write_text(text)

def put_mech(data):
    rc, out, err = run_trace("put-mechanisms", F, input_text=data)
    if rc != 0:
        print(f"  put_mech stderr: {err}", file=sys.stderr)
    return rc

def hasrow(spec_id, task_ids, files, source):
    if not TT.exists():
        return False
    target = f"{spec_id}{TAB}{task_ids}{TAB}{files}{TAB}{source}"
    return target in TT.read_text()

def datacount():
    if not TT.exists():
        return -1
    lines = TT.read_text().splitlines()
    count = 0
    for line in lines[2:]:
        if line.strip():
            count += 1
    return count

# ── Tests ────────────────────────────────────────────────────────────────────

reset_feature()

# 1. refs from field 2 only; gloss id not grepped; files from path
rc = put_mech(f"AC-001{TAB}direct{TAB}lock{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | AC-001 | gloss mentioning AC-999 in prose
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and hasrow("AC-001", "T001", "src/a.js", "tasks.md") and "AC-999" not in TT.read_text():
    ok("refs from field 2; gloss not grepped; files from path")
else:
    no("basic", f"rc={rc} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 2. one id covered by two tasks → task_ids joined with ';'
rc = put_mech(f"AC-001{TAB}direct{TAB}lock{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | AC-001 | first
- [x] T002 [US1] | src/a.js | AC-001 | second
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and hasrow("AC-001", "T001;T002", "src/a.js", "tasks.md"):
    ok("id covered by two tasks → task_ids joined ';'")
else:
    no("two tasks one id", f"rc={rc} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 3. multiple refs in one task → separate rows per id
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"AC-002{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | REQ-001,AC-002 | two refs
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and hasrow("REQ-001", "T001", "src/a.js", "tasks.md") and hasrow("AC-002", "T001", "src/a.js", "tasks.md"):
    ok("multiple refs → row per id")
else:
    no("multi-ref", f"rc={rc} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 4. infra line + empty refs contribute nothing
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] run build, no coverage
- [ ] T002 [US1] | src/a.js | REQ-001 | covers it
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and datacount() == 1 and hasrow("REQ-001", "T002", "src/a.js", "tasks.md"):
    ok("infra/empty-refs → no rows")
else:
    no("infra", f"rc={rc} rows={datacount()} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 5. documented mechanism → plan.md row (empty task_ids), no task
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"NFR-001{TAB}documented{TAB}budget{TAB}docs/p.md{TAB}documented\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | REQ-001 | covers req
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and hasrow("NFR-001", "", "docs/p.md", "plan.md") and hasrow("REQ-001", "T001", "src/a.js", "tasks.md"):
    ok("documented → plan.md row, empty task_ids")
else:
    no("documented", f"rc={rc} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 6. COVERAGE: direct mechanism with no task → reject, file untouched
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"INV-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}integration\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | REQ-001 | INV-001 left uncovered
""")
before = TT.read_text() if TT.exists() else ""
rc, out, err = run_trace("extract-trace", F)
after = TT.read_text() if TT.exists() else ""
if rc != 0 and before == after:
    ok("direct without task → coverage reject, untouched")
else:
    no("coverage reject", f"rc={rc}")

# 7. documented id given a task → reject
rc = put_mech(f"NFR-001{TAB}documented{TAB}b{TAB}docs/p.md{TAB}documented\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | NFR-001 | wrongly tasking documented id
""")
rc, out, err = run_trace("extract-trace", F)
if rc != 0:
    ok("documented id with task → reject")
else:
    no("documented-with-task", f"rc={rc} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 8. delegated: AC-002 delegated to AC-001, only AC-001 tasked
rc = put_mech(f"AC-001{TAB}direct{TAB}lock{TAB}src/a.js{TAB}unit\n"
              f"AC-002{TAB}delegated:AC-001{TAB}same{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | AC-001 | AC-002 delegates to this
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and hasrow("AC-001", "T001", "src/a.js", "tasks.md"):
    ok("delegated satisfied by delegate's task")
else:
    no("delegated", f"rc={rc} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 9. strict task anchor: only the valid line matched
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""* [ ] T001 [US1] | src/a.js | REQ-001 | star bullet
- [ ] TODO [US1] | src/a.js | REQ-001 | no T-number
- [ ] T001 [US1] | src/a.js | REQ-001 | the valid one
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and datacount() == 1 and hasrow("REQ-001", "T001", "src/a.js", "tasks.md"):
    ok("strict anchor: only valid line")
else:
    no("strict", f"rc={rc} rows={datacount()} :: {TT.read_text() if TT.exists() else 'N/A'}")

# 10. duplicate ref within one task → reject
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | REQ-001,REQ-001 | same id twice
""")
rc, out, err = run_trace("extract-trace", F)
if rc != 0:
    ok("duplicate ref within task → reject")
else:
    no("dup ref", f"rc={rc}")

# 11. kitchen-sink: task driving >3 spec ids → reject (atomicity cap in parser)
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"REQ-002{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"REQ-003{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"REQ-004{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | REQ-001,REQ-002,REQ-003,REQ-004 | four driving ids
""")
before = TT.read_text() if TT.exists() else ""
rc, out, err = run_trace("extract-trace", F)
after = TT.read_text() if TT.exists() else ""
if rc != 0 and before == after:
    ok("task driving >3 spec ids → reject (cap), untouched")
else:
    no("cap-3", f"rc={rc}")

# 12. exactly 3 driving ids → allowed (boundary)
rc = put_mech(f"REQ-001{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"REQ-002{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n"
              f"REQ-003{TAB}direct{TAB}m{TAB}src/a.js{TAB}unit\n")
if rc != 0:
    no("put_mech seed", f"rc={rc}")
write_tasks("""- [ ] T001 [US1] | src/a.js | REQ-001,REQ-002,REQ-003 | exactly three driving ids
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0 and hasrow("REQ-001", "T001", "src/a.js", "tasks.md") and hasrow("REQ-003", "T001", "src/a.js", "tasks.md"):
    ok("exactly 3 driving ids → allowed")
else:
    no("cap-3 boundary", f"rc={rc} :: {TT.read_text() if TT.exists() else 'N/A'}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)