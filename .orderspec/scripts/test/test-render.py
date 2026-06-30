#!/usr/bin/env python3
"""test-render.py — regression for render + stale guard + Variant C"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
TRACE = SCRIPT_DIR.parent / "traceability.py"

if not TRACE.exists():
    print(f"FATAL: traceability.py not found at {TRACE}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────
LOG_TO_FILE = False  # Set to True to also write test results to test/test-render.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-render.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
SPECS_ROOT = WORK / "specs"
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-render-{os.getpid()}"
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

def mech(data):
    rc, out, err = run_trace("put-mechanisms", F, input_text=data)
    return rc

# ── Tests ────────────────────────────────────────────────────────────────────

# basic render (direct + documented)
reset_feature()
mech(f"REQ-001{TAB}direct{TAB}validate email{TAB}src/a.js{TAB}unit\n"
     f"NFR-001{TAB}documented{TAB}p95 < 200ms{TAB}docs/perf.md{TAB}documented\n")
(SPECS / "tasks.md").write_text("""- [ ] T012 [US1] | src/a.js | REQ-001 | validate email
""")
run_trace("extract-trace", F)

rc, out, err = run_trace("render", F)
md = (SDIR / "traceability.md").read_text() if (SDIR / "traceability.md").exists() else ""
if rc == 0 and "DO NOT EDIT" in md and "REQ-001" in md and "NFR-001" in md and "2 mechanisms · 1 direct · 1 documented" in md:
    ok("render → banner + rows + computed counts")
else:
    no("render basic", f"rc={rc}")

if "| NFR-001 | documented | — |" in md:
    ok("documented row → tasks shown as —")
else:
    no("documented dash", "not present")

prev = md
(SDIR / "traceability.tsv").write_text("broken marker\n")
rc, out, err = run_trace("render", F)
now = (SDIR / "traceability.md").read_text() if (SDIR / "traceability.md").exists() else ""
if rc == 2 and prev == now:
    ok("corrupt source → exit 2, old mirror untouched")
else:
    no("corrupt source", f"rc={rc}")

reset_feature()
rc, out, err = run_trace("render", F)
if rc != 0 and not (SDIR / "traceability.md").exists():
    ok("missing source → nonzero, no mirror")
else:
    no("missing source", f"rc={rc}")

# stale-guard
reset_feature()
mech(f"REQ-001{TAB}direct{TAB}validate email{TAB}src/a.js{TAB}unit\n")
(SPECS / "tasks.md").write_text("""- [ ] T012 [US1] | src/a.js | REQ-001 | validate email
""")
run_trace("extract-trace", F)
run_trace("render", F)

rc, out, err = run_trace("render", F)
if rc == 0:
    ok("fresh projection → render ok")
else:
    no("fresh render", f"rc={rc}")

time.sleep(1)
(SPECS / "tasks.md").touch()
prev = (SDIR / "traceability.md").read_text() if (SDIR / "traceability.md").exists() else ""
rc, out, err = run_trace("render", F)
now = (SDIR / "traceability.md").read_text() if (SDIR / "traceability.md").exists() else ""
if rc == 2 and prev == now:
    ok("stale (tasks.md newer) → render refuses, mirror untouched")
else:
    no("stale newer", f"rc={rc}")

rc, out, err = run_trace("get", F, "trace")
if rc != 0 and "stale" in err:
    ok("stale → get trace refuses (nonzero)")
else:
    no("stale get trace", f"rc={rc} err={err}")

run_trace("extract-trace", F)
rc, out, err = run_trace("render", F)
rc2, out2, err2 = run_trace("get", F, "trace")
if rc == 0 and rc2 == 0:
    ok("after re-extract → fresh, render+get ok")
else:
    no("reproject", f"rc={rc} rc2={rc2}")

prev = (SDIR / "traceability.md").read_text() if (SDIR / "traceability.md").exists() else ""
(SPECS / "tasks.md").unlink()
rc, out, err = run_trace("render", F)
now = (SDIR / "traceability.md").read_text() if (SDIR / "traceability.md").exists() else ""
if rc == 2 and prev == now:
    ok("tasks.md gone, derived remains → render refuses, mirror untouched")
else:
    no("gone-source render", f"rc={rc}")

rc, out, err = run_trace("get", F, "trace")
if rc != 0 and "stale" in err:
    ok("tasks.md gone → get trace refuses")
else:
    no("gone-source get", f"rc={rc}")

reset_feature()
mech(f"REQ-001{TAB}direct{TAB}x{TAB}src/a.js{TAB}unit\n")
(SPECS / "tasks.md").write_text("""- [ ] T012 [US1] | src/a.js | REQ-001 | x
""")
rc, out, err = run_trace("render", F)
if rc != 0 and not (SDIR / "traceability.md").exists():
    ok("no projection yet → render 'missing' path (not stale crash)")
else:
    no("no-projection render", f"rc={rc}")

# Variant C: ref subset / empty-ref contract
reset_feature()
mech(f"REQ-001{TAB}direct{TAB}task schema{TAB}src/models/task.model.js{TAB}unit\n"
     f"REQ-002{TAB}direct{TAB}audit schema{TAB}src/models/auditLog.model.js{TAB}unit\n")

# C1: empty refs on an infra/barrel task is LEGAL → extract-trace rc=0
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.js | REQ-001 | task schema
- [ ] T002 | src/models/auditLog.model.js | REQ-002 | audit schema
- [ ] T003 | src/models/index.js |  | register models in barrel
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0:
    ok("empty refs on infra task → extract-trace rc=0")
else:
    no("C1 empty refs", f"rc={rc} err={err}")

# C2: filler ref (REQ-001 on index.js, not in its primary_files) → rejected rc=3
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.js | REQ-001 | task schema
- [ ] T002 | src/models/auditLog.model.js | REQ-002 | audit schema
- [ ] T003 | src/models/index.js | REQ-001 | register models in barrel
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 3:
    ok("filler ref (path not in primary_files) → rc=3")
else:
    no("C2 filler ref", f"rc={rc} err={err}")

# C3: declared ref on its TRUE primary_files path → accepted rc=0
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.js | REQ-001 | task schema
- [ ] T002 | src/models/auditLog.model.js | REQ-002 | audit schema
""")
rc, out, err = run_trace("extract-trace", F)
rc2, out2, err2 = run_trace("get", F, "trace")
if rc == 0 and f"REQ-001{TAB}T001{TAB}src/models/task.model.js{TAB}tasks.md" in out2:
    ok("true-path ref → accepted, trace bound correctly")
else:
    no("C3 true-path ref", f"rc={rc} trace={out2}")

# C4: god-file sub-file granularity preserved (two refs on same shared file)
reset_feature()
mech(f"REQ-006{TAB}direct{TAB}update guard{TAB}src/services/task.service.js{TAB}integration\n"
     f"REQ-007{TAB}direct{TAB}soft delete{TAB}src/services/task.service.js{TAB}integration\n")
(SPECS / "tasks.md").write_text("""- [ ] T010 | src/services/task.service.js | REQ-006 | update with guard
- [ ] T011 | src/services/task.service.js | REQ-007 | soft delete
""")
rc, out, err = run_trace("extract-trace", F)
rc2, out2, err2 = run_trace("get", F, "trace")
if rc == 0 and "REQ-006" in out2 and "REQ-007" in out2:
    ok("god-file: each ref binds to its own task (granularity kept)")
else:
    no("C4 god-file", f"rc={rc} trace={out2}")

# C5: delegated AC id as a ref → rejected rc=3
reset_feature()
mech(f"REQ-003{TAB}direct{TAB}create{TAB}src/services/task.service.js{TAB}integration\n"
     f"AC-001{TAB}delegated:REQ-003{TAB}delegated to REQ-003{TAB}src/services/task.service.js{TAB}integration\n")
(SPECS / "tasks.md").write_text("""- [ ] T005 | tests/integration/task.test.py | AC-001 | integration test
- [ ] T007 | src/services/task.service.py | REQ-003 | create task
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 3:
    ok("delegated AC id as ref → rc=3")
else:
    no("C5 delegated ref", f"rc={rc} err={err}")

# C6: documented id as a ref → rejected rc=3
reset_feature()
mech(f"REQ-001{TAB}direct{TAB}schema{TAB}src/models/task.model.js{TAB}unit\n"
     f"REQ-010{TAB}documented{TAB}no delete endpoint{TAB}documented{TAB}documented\n")
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.js | REQ-001 | schema
- [ ] T099 | src/models/task.model.js | REQ-010 | wrongly tasking documented id
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 3:
    ok("documented id as ref → rc=3")
else:
    no("C6 documented ref", f"rc={rc} err={err}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)