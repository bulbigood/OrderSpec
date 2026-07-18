#!/usr/bin/env python3
"""test-validate.py — tests for traceability.py"""

import json
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
LOG_TO_FILE = False

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-validate.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
sys.path.insert(0, str(SCRIPT_DIR.parent))
from common import FEATURES_DIR
SPECS_ROOT = WORK / FEATURES_DIR
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-validate-{os.getpid()}"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".state"

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

def cleanup_repo():
    src = WORK / "src"
    if src.exists():
        shutil.rmtree(src, ignore_errors=True)

def reset_feature():
    if SPECS.exists():
        shutil.rmtree(SPECS, ignore_errors=True)
    SPECS.mkdir(parents=True, exist_ok=True)
    cleanup_repo()
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

TAB = "\t"

def put_mechanisms(*rows):
    text = "\n".join(rows)
    if text and not text.endswith("\n"):
        text += "\n"
    return run_trace("put-mechanisms", F, input_text=text)


VALID_SPEC_FRONTMATTER = """---
orderspec:
  artifact: spec
  feature_id: FEAT-001-test-validate
  slug: test-validate
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: test-model
---
"""


def write_spec(body):
    """Write spec.md with valid Phase 2 OrderSpec YAML frontmatter."""
    (SPECS / "spec.md").write_text(
        VALID_SPEC_FRONTMATTER + body,
        encoding="utf-8",
    )

# ── check-plan tests ─────────────────────────────────────────────────────────

# C1: missing pathmanifest → exit 1
reset_feature()
(SPECS / "plan.md").write_text("")
rc, out, err = run_trace("check-plan", F)
if rc == 1:
    ok("check-plan: missing pathmanifest → exit 1")
else:
    no("check-plan missing manifest", f"rc={rc}")

# C2: [MOD] on existing file → OK
reset_feature()
path = WORK / "src" / "models" / "user.py"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [MOD]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 0:
    ok("check-plan: [MOD] existing → OK")
else:
    no("check-plan mod existing", f"rc={rc}")

# C3: [MOD] on missing file → exit 1
reset_feature()
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [MOD]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 1:
    ok("check-plan: [MOD] missing → exit 1")
else:
    no("check-plan mod missing", f"rc={rc}")

# C4: [NEW] on missing file → OK
reset_feature()
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 0:
    ok("check-plan: [NEW] missing → OK")
else:
    no("check-plan new missing", f"rc={rc}")

# C5: [NEW] on existing file → exit 1
reset_feature()
path = WORK / "src" / "models" / "user.py"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 1:
    ok("check-plan: [NEW] existing → exit 1")
else:
    no("check-plan new existing", f"rc={rc}")

# C6: directory in manifest → exit 1
reset_feature()
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/  [NEW]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 1:
    ok("check-plan: directory → exit 1")
else:
    no("check-plan directory", f"rc={rc}")

# C7: missing tag → exit 1
reset_feature()
path = WORK / "src" / "models" / "user.py"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 1:
    ok("check-plan: missing tag → exit 1")
else:
    no("check-plan missing tag", f"rc={rc}")

# C8: mixed manifest → only bad rows reported
reset_feature()
path = WORK / "src" / "models" / "user.py"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("")
path2 = WORK / "src" / "services" / "auth.py"
path2.parent.mkdir(parents=True, exist_ok=True)
path2.write_text("")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py     [MOD]
src/services/auth.py   [NEW]
src/api/routes.py      [MOD]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 1 and "routes.py" in err:
    ok("check-plan: mixed manifest reports only bad rows")
else:
    no("check-plan mixed", f"rc={rc} err={err}")

# ── validate tests ───────────────────────────────────────────────────────────

# V1: clean spec → exit 0
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0:
    ok("validate: clean spec → exit 0")
else:
    no("validate clean spec", f"rc={rc} out={out} err={err}")

# V2: REQ without Covers → M1
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: (none)
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 1 and "M1" in out:
    ok("validate: REQ without Covers → M1")
else:
    no("validate M1", f"rc={rc} out={out} err={err}")

# V3: dangling plan ref → M5
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
```
See also REQ-999.
""")
rc, out, err = run_trace("validate", "--stage", "plan", F)
if rc == 1 and "M5" in out:
    ok("validate: dangling plan ref → M5")
else:
    no("validate M5 plan", f"rc={rc} out={out} err={err}")

# V4: [MOD] missing file → M10
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [MOD]
```
""")
rc, out, err = run_trace("validate", "--stage", "plan", F)
if rc == 1 and "M10" in out:
    ok("validate: [MOD] missing → M10")
else:
    no("validate M10", f"rc={rc} out={out} err={err}")

# V_CONFIG_B_1: mechanism primary file not in pathmanifest → M16
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
```
""")
put_mechanisms(
    f"REQ-001{TAB}direct{TAB}login service{TAB}src/services/auth.py{TAB}unit",
)
rc, out, err = run_trace("validate", "--stage", "plan", F)
if rc == 1 and "M16" in out:
    ok("validate: mechanism primary file not in manifest → M16")
else:
    no("validate M16", f"rc={rc} out={out} err={err}")

# V4b: tasks stage accepts an applied [NEW] transition from the frozen baseline
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
(WORK / "src" / "models").mkdir(parents=True, exist_ok=True)
(WORK / "src" / "models" / "user.py").write_text("class User: pass\n")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
tests/unit/user.test.py  [NEW]
```
""")
put_mechanisms(
    f"REQ-001{TAB}direct{TAB}login model{TAB}src/models/user.py{TAB}unit",
)
(SPECS / "tasks.md").write_text("""- [X] T001 [US1] | src/models/user.py | REQ-001 | user model
- [X] T002 [US1] | tests/unit/user.test.py |  | unit evidence path
""")
rc, out, err = run_trace("validate", "--stage", "tasks", F)
if rc == 0 and "M10" not in out:
    ok("validate: tasks stage accepts applied [NEW] baseline transition")
else:
    no("validate tasks applied transition", f"rc={rc} out={out} err={err}")

rc, out, err = run_trace("validate", "--stage", "plan", F)
if rc == 1 and "M10" in out:
    ok("validate: plan stage still rejects existing [NEW] baseline path")
else:
    no("validate plan baseline M10", f"rc={rc} out={out} err={err}")

# V_CONFIG_B_2: documented primary file outside plan.md or manifest → M26
reset_feature()
write_spec("""- **REQ-001** user can log in
- **NFR-001** audit decision is documented
- **UJ-001** Login journey
  Covers: REQ-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
tests/unit/user.test.py  [NEW]
```
""")
put_mechanisms(
    f"REQ-001{TAB}direct{TAB}login model{TAB}src/models/user.py{TAB}unit",
    f"NFR-001{TAB}documented{TAB}documented audit decision{TAB}docs/audit.md{TAB}documented",
)
rc, out, err = run_trace("validate", "--stage", "plan", F)
if rc == 0 and "M26" in out:
    ok("validate: documented primary file outside manifest → M26")
else:
    no("validate M26", f"rc={rc} out={out} err={err}")

# V5: uncovered AC → M2
reset_feature()
write_spec("""- **REQ-001** user can log in
- **AC-001** [Covers: REQ-001] valid creds return 200
- **UJ-001** Login journey
  Covers: REQ-001, AC-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
```
""")
put_mechanisms(
    f"REQ-001{TAB}direct{TAB}login model{TAB}src/models/user.py{TAB}unit",
    f"AC-001{TAB}direct{TAB}valid credential acceptance path{TAB}src/models/user.py{TAB}unit",
)
(SPECS / "tasks.md").write_text("""- [ ] T001 [US1] | src/models/user.py | REQ-001 | user model
""")
rc, out, err = run_trace("validate", "--stage", "tasks", F)
if rc == 1 and "M2" in out:
    ok("validate: uncovered AC → M2")
else:
    no("validate M2", f"rc={rc} out={out} err={err}")

# V6: placeholder → M13 (LOW severity, rc=0)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
TODO: finish this
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M13" in out:
    ok("validate: placeholder → M13")
else:
    no("validate M13", f"rc={rc} out={out} err={err}")

rc, out, err = run_trace("validate", "--json", "--stage", "spec", F)
summary = json.loads(out)["summary"]
if (
    rc == 0
    and summary["verdict_floor"] == "ROUTING_REQUIRED"
    and summary["pass_allowed"] is False
    and summary["block_required"] is False
):
    ok("validate: routed LOW finding sets ROUTING_REQUIRED floor")
else:
    no("validate LOW verdict floor", f"rc={rc} summary={summary}")

# V7: JSON output
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
rc, out, err = run_trace("validate", "--json", "--stage", "spec", F)
try:
    parsed = json.loads(out)
    if rc == 0 and parsed["stage"] == "spec" and parsed["summary"]["exit_code"] == 0:
        ok("validate: JSON output valid")
    else:
        no("validate JSON", f"out={out}")
except json.JSONDecodeError:
    no("validate JSON", f"rc={rc} out={out} err={err}")

# V7b: routed HIGH finding sets BLOCK floor
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
- **Q-001** unresolved blocking question
""")
rc, out, err = run_trace("validate", "--json", "--stage", "spec", F)
summary = json.loads(out)["summary"]
if (
    rc == 1
    and summary["verdict_floor"] == "BLOCK"
    and summary["pass_allowed"] is False
    and summary["block_required"] is True
):
    ok("validate: routed HIGH finding sets BLOCK floor")
else:
    no("validate HIGH verdict floor", f"rc={rc} summary={summary}")

# V8: task gap → no M7 (gaps are allowed)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
tests/unit/user.test.py  [NEW]
```
""")
put_mechanisms(
    f"REQ-001{TAB}direct{TAB}login model{TAB}src/models/user.py{TAB}unit",
)
(SPECS / "tasks.md").write_text("""- [ ] T001 [US1] | src/models/user.py | REQ-001 | user model
- [ ] T003 [US1] | src/models/user.py | REQ-001 | another task
- [ ] T005 [US1] | tests/unit/user.test.py |  | unit evidence path
""")
rc, out, err = run_trace("validate", "--stage", "tasks", F)
if rc == 0 and "M7" not in out:
    ok("validate: task gap allowed (no M7)")
else:
    no("validate M7 gap", f"rc={rc} out={out} err={err}")

# V9: [USn] without matching UJ → M14
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
```
""")
put_mechanisms(
    f"REQ-001{TAB}direct{TAB}login model{TAB}src/models/user.py{TAB}unit",
)
(SPECS / "tasks.md").write_text("""- [ ] T001 [US2] | src/models/user.py | REQ-001 | user model
""")
rc, out, err = run_trace("validate", "--stage", "tasks", F)
if rc == 1 and "M14" in out:
    ok("validate: [US2] without UJ-002 → M14")
else:
    no("validate M14", f"rc={rc} out={out} err={err}")

# V10: dangling task ref → M5
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
""")
(SPECS / "plan.md").write_text("""```pathmanifest
src/models/user.py  [NEW]
```
""")
put_mechanisms(
    f"REQ-001{TAB}direct{TAB}login model{TAB}src/models/user.py{TAB}unit",
)
(SPECS / "tasks.md").write_text("""- [ ] T001 [US1] | src/models/user.py | REQ-999 | user model
""")
rc, out, err = run_trace("validate", "--stage", "tasks", F)
if rc == 1 and "M5" in out:
    ok("validate: dangling task ref → M5")
else:
    no("validate M5 task", f"rc={rc} out={out} err={err}")

# V_M18: missing IF fields → M18 (HIGH)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 9. Interface Contracts
- **IF-001**: Get Task
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 1 and "M18" in out:
    ok("validate: missing IF fields → M18")
else:
    no("validate M18", f"rc={rc} out={out} err={err}")

# V_M19: IF-AC status mismatch in an unprioritized journey → M19 (MEDIUM)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 9. Interface Contracts
- **IF-001**: Get Task
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Get Task |
  | Actor | Authenticated user |
  | Success | 200 OK |
  | Failure | 404 Not Found |
  | Covers | REQ-001 |
## 12. Acceptance Criteria
- **UJ-002** Journey
  Covers: REQ-001
  - **AC-001** [Covers: IF-001] returns 500
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if "M19" in out:
    ok("validate: IF-AC status mismatch → M19")
else:
    no("validate M19", f"rc={rc} out={out} err={err}")

# V_M19_P1: the same mismatch in a P1 journey → M19 (HIGH)
reset_feature()
write_spec("""- **REQ-001** user can log in
## 9. Interface Contracts
- **IF-001**: Get Task
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Get Task |
  | Actor | Authenticated user |
  | Success | 200 OK |
  | Failure | 404 Not Found |
  | Covers | REQ-001 |
## 12. Acceptance Criteria
- **UJ-001** Journey (Priority: P1)
  Covers: REQ-001
  - **AC-001** [Covers: REQ-001, IF-001] returns 500
""")
rc, out, err = run_trace("validate", "--json", "--stage", "spec", F)
m19 = [f for f in json.loads(out)["findings"] if f["check"] == "M19"]
if m19 and all(f["severity"] == "HIGH" for f in m19):
    ok("validate: P1 IF-AC status mismatch → M19 HIGH")
else:
    no("validate P1 M19 severity", f"rc={rc} findings={m19}")

# V_M20: IF uncovered by AC → M20 (HIGH)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 9. Interface Contracts
- **IF-001**: Get Task
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Get Task |
  | Actor | Authenticated user |
  | Success | 200 OK |
  | Failure | 404 Not Found |
  | Covers | REQ-001 |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 1 and "M20" in out:
    ok("validate: IF uncovered by AC → M20")
else:
    no("validate M20", f"rc={rc} out={out} err={err}")

# V_M22: AC field alignment → M22 (LOW)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 8. Information Model
### Entity: Task
| Field | Type |
|-------|------|
| title | string |
## 12. Acceptance Criteria
- **UJ-002** Journey
  Covers: REQ-001
  - **AC-001** [Covers: REQ-001] response contains `nonExistentField`
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M22" in out:
    ok("validate: AC field alignment → M22")
else:
    no("validate M22", f"rc={rc} out={out} err={err}")

# V_M23: Grid reference validity → M23 (MEDIUM)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 10. Invariants
### Contradiction Grid
| INV | Source | Verdict |
|-----|--------|---------|
| INV-999 × NFR-001 | INV-999 defines X | Compatible |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M23" in out:
    ok("validate: Grid reference validity → M23")
else:
    no("validate M23", f"rc={rc} out={out} err={err}")

# V_M24: Grid completeness → M24 (MEDIUM)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 10. Invariants
- **INV-001**: Always do X.
### Contradiction Grid
| INV | Source | Verdict |
|-----|--------|---------|
| NFR-001 × REQ-001 | NFR-001 requires Y | Compatible |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M24" in out:
    ok("validate: Grid completeness → M24")
else:
    no("validate M24", f"rc={rc} out={out} err={err}")

# V_M25: duplicate grid rows with ID in 2nd column → M25 (MEDIUM)
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 10. Invariants
- **INV-001**: Always do X.
- **NFR-001**: Must be fast.
### Contradiction Grid
| INV | Source | Verdict |
|-----|--------|---------|
| INV-001 × NFR-001 | INV-001 defines state; NFR-001 requires consistency | Compatible |
| INV-001 × NFR-001 | INV-001 defines state; NFR-001 requires consistency | Compatible |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M25" in out:
    ok("validate: duplicate grid rows (3-col) → M25")
else:
    no("validate M25", f"rc={rc} out={out} err={err}")

# ── extract-trace / render round-trip ────────────────────────────────────────

# ── Variant C: ref subset / empty-ref contract ──────────────────────────────

# V13: empty refs on infra task is LEGAL
reset_feature()
mech_data = f"REQ-001{TAB}direct{TAB}task schema{TAB}src/models/task.model.py{TAB}unit\n"
mech_data += f"REQ-002{TAB}direct{TAB}audit schema{TAB}src/models/auditLog.model.py{TAB}unit"
run_trace("put-mechanisms", F, input_text=mech_data)
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.py | REQ-001 | task schema
- [ ] T002 | src/models/auditLog.model.py | REQ-002 | audit schema
- [ ] T003 | src/models/index.js |  | register models in barrel
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 0:
    ok("empty refs on infra task → extract-trace rc=0")
else:
    no("C1 empty refs", f"rc={rc} out={out} err={err}")

# V14: filler ref → rc=3
reset_feature()
run_trace("put-mechanisms", F, input_text=mech_data)
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.py | REQ-001 | task schema
- [ ] T002 | src/models/auditLog.model.py | REQ-002 | audit schema
- [ ] T003 | src/models/index.js | REQ-001 | register models in barrel
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 3:
    ok("filler ref (path not in primary_files) → rc=3")
else:
    no("C2 filler ref", f"rc={rc} out={out} err={err}")

# V15: true-path ref → accepted
reset_feature()
run_trace("put-mechanisms", F, input_text=mech_data)
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.py | REQ-001 | task schema
- [ ] T002 | src/models/auditLog.model.py | REQ-002 | audit schema
""")
rc, out, err = run_trace("extract-trace", F)
rc2, out2, err2 = run_trace("get", F, "trace")
if rc == 0 and f"REQ-001{TAB}T001" in out2:
    ok("true-path ref → accepted, trace bound correctly")
else:
    no("C3 true-path ref", f"rc={rc} trace={out2}")

# V16: god-file sub-file granularity
reset_feature()
mech2 = f"REQ-006{TAB}direct{TAB}update guard{TAB}src/services/task.service.py{TAB}integration\n"
mech2 += f"REQ-007{TAB}direct{TAB}soft delete{TAB}src/services/task.service.py{TAB}integration"
run_trace("put-mechanisms", F, input_text=mech2)
(SPECS / "tasks.md").write_text("""- [ ] T010 | src/services/task.service.py | REQ-006 | update with guard
- [ ] T011 | src/services/task.service.py | REQ-007 | soft delete
""")
rc, out, err = run_trace("extract-trace", F)
rc2, out2, err2 = run_trace("get", F, "trace")
if rc == 0 and "REQ-006" in out2 and "REQ-007" in out2:
    ok("god-file: each ref binds to its own task")
else:
    no("C4 god-file", f"rc={rc} trace={out2}")

# V17: delegated AC id as ref → rc=3
reset_feature()
mech3 = f"REQ-003{TAB}direct{TAB}create{TAB}src/services/task.service.py{TAB}integration\n"
mech3 += f"AC-001{TAB}delegated:REQ-003{TAB}delegated to REQ-003{TAB}src/services/task.service.py{TAB}integration"
run_trace("put-mechanisms", F, input_text=mech3)
(SPECS / "tasks.md").write_text("""- [ ] T005 | tests/integration/task.test.py | AC-001 | integration test
- [ ] T007 | src/services/task.service.py | REQ-003 | create task
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 3:
    ok("delegated AC id as ref → rc=3")
else:
    no("C5 delegated ref", f"rc={rc} out={out} err={err}")

# V18: documented id as ref → rc=3
reset_feature()
mech4 = f"REQ-001{TAB}direct{TAB}schema{TAB}src/models/task.model.py{TAB}unit\n"
mech4 += f"REQ-010{TAB}documented{TAB}no delete endpoint{TAB}documented{TAB}documented"
run_trace("put-mechanisms", F, input_text=mech4)
(SPECS / "tasks.md").write_text("""- [ ] T001 | src/models/task.model.py | REQ-001 | schema
- [ ] T099 | src/models/task.model.py | REQ-010 | wrongly tasking documented id
""")
rc, out, err = run_trace("extract-trace", F)
if rc == 3:
    ok("documented id as ref → rc=3")
else:
    no("C6 documented ref", f"rc={rc} out={out} err={err}")


# ── New tests for M13 expansion and M30 ─────────────────────────────────────

# V_M13_1: semicolon-separated in IF Failure → M13
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 9. Interface Contracts
- **IF-001**: Get Task
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Get Task |
  | Actor | Authenticated user |
  | Success | 200 OK |
  | Failure | 404 Not Found; semicolon-separated |
  | Covers | REQ-001 |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if "M13" in out:
    ok("validate: semicolon-separated in Failure -> M13")
else:
    no("validate M13 semi", f"rc={rc} out={out} err={err}")

# V_M13_2: None (...) in IF Failure → M13
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 9. Interface Contracts
- **IF-001**: Get Task
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Get Task |
  | Actor | Authenticated user |
  | Success | 200 OK |
  | Failure | None (empty array returned) |
  | Covers | REQ-001 |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if "M13" in out:
    ok("validate: None (...) in Failure -> M13")
else:
    no("validate M13 None", f"rc={rc} out={out} err={err}")

# V_M13_3: [Failure outcomes] placeholder in IF Failure → M13
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 9. Interface Contracts
- **IF-001**: Get Task
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Get Task |
  | Actor | Authenticated user |
  | Success | 200 OK |
  | Failure | [Failure outcomes] |
  | Covers | REQ-001 |
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if "M13" in out:
    ok("validate: [Failure outcomes] placeholder -> M13")
else:
    no("validate M13 placeholder", f"rc={rc} out={out} err={err}")

# V_M30_1: EDGE without AC coverage and not deferred → M30
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 11. Edge Cases
- **EDGE-001**: Concurrent update to the same task by the same user
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M30" in out:
    ok("validate: EDGE without AC/deferred -> M30")
else:
    no("validate M30 uncovered", f"rc={rc} out={out} err={err}")

# V_M30_2: EDGE with deferred marker → no M30
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 11. Edge Cases
- **EDGE-001**: Concurrent update -> deferred (waiting for transaction implementation)
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M30" not in out:
    ok("validate: EDGE with deferred -> no M30")
else:
    no("validate M30 deferred", f"rc={rc} out={out} err={err}")

# V_M30_3: EDGE covered by AC → no M30
reset_feature()
write_spec("""- **REQ-001** user can log in
- **UJ-001** Login journey
  Covers: REQ-001
## 11. Edge Cases
- **EDGE-001**: Concurrent update -> covered by AC-001
## 12. Acceptance Criteria
- **UJ-002** Journey
  Covers: REQ-001
  - **AC-001** [Covers: REQ-001] handles concurrent update
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 0 and "M30" not in out:
    ok("validate: EDGE covered by AC -> no M30")
else:
    no("validate M30 covered", f"rc={rc} out={out} err={err}")

# ── Contract-risk checks ─────────────────────────────────────────────────────

# V_M33: exact-one audit guarantee without failure semantics → M33
reset_feature()
write_spec("""- **REQ-001** every task mutation creates exactly one audit log entry
- **UJ-001** Task journey
  Covers: REQ-001
## 10. Invariants
- **INV-001** every mutation MUST produce exactly one audit entry
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 1 and "M33" in out:
    ok("validate: exact-one audit without failure semantics -> M33")
else:
    no("validate M33", f"rc={rc} out={out} err={err}")

# V_M34: pagination in a P1 interface without envelope → M34 HIGH
reset_feature()
write_spec("""- **REQ-001** user can list tasks
## 9. Interface Contracts
- **IF-001**: List tasks
  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | List tasks |
  | Actor | Authenticated user |
  | Input | Optional pagination |
  | Success | Returns 200 with an array |
  | Failure | Returns 401 |
  | Covers | REQ-001 |
## 12. Acceptance Criteria
- **UJ-001** Task journey (Priority: P1)
  Covers: REQ-001
  - **AC-001** [Covers: REQ-001, IF-001] returns 200 or 401
""")
rc, out, err = run_trace("validate", "--json", "--stage", "spec", F)
parsed = json.loads(out)
m34 = [f for f in parsed["findings"] if f["check"] == "M34"]
if rc == 1 and m34 and m34[0]["severity"] == "HIGH":
    ok("validate: bare P1 pagination input -> M34 HIGH")
else:
    no("validate P1 M34", f"rc={rc} findings={m34} err={err}")

# V_M34_P2: the same gap outside P1 → M34 MEDIUM
write_spec((SPECS / "spec.md").read_text().replace("Priority: P1", "Priority: P2"))
rc, out, err = run_trace("validate", "--json", "--stage", "spec", F)
parsed = json.loads(out)
m34 = [f for f in parsed["findings"] if f["check"] == "M34"]
if m34 and m34[0]["severity"] == "MEDIUM":
    ok("validate: bare non-P1 pagination input -> M34 MEDIUM")
else:
    no("validate non-P1 M34", f"rc={rc} findings={m34} err={err}")

# V_M35: newly-created empty audit history contradicts creation audit
reset_feature()
write_spec("""- **REQ-001** system creates an audit log entry for every task creation
- **UJ-001** Task journey
  Covers: REQ-001
## 11. Edge Cases
- **EDGE-001** newly created task has no audit history and returns an empty array
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 1 and "M35" in out:
    ok("validate: empty new audit history contradicts creation audit -> M35")
else:
    no("validate M35", f"rc={rc} out={out} err={err}")

# V_M36: changed fields versus full snapshots → M36
reset_feature()
write_spec("""- **REQ-001** update audit records changed fields with before/after values
- **UJ-001** Task journey
  Covers: REQ-001
## 14. Decisions
- **DEC-001** audit records use full entity snapshots
  - **Affects**: REQ-001
  - **Rationale**: preserve complete state
""")
rc, out, err = run_trace("validate", "--stage", "spec", F)
if rc == 1 and "M36" in out:
    ok("validate: changed fields versus full snapshots -> M36")
else:
    no("validate M36", f"rc={rc} out={out} err={err}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
