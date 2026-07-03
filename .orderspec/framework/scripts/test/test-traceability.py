#!/usr/bin/env python3
"""test-traceability.py — regression for traceability.py validate command."""

import json
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

WORK = Path(tempfile.mkdtemp(prefix="orderspec-trace-"))
sys.path.insert(0, str(SCRIPT_DIR.parent))
from common import FEATURES_DIR

SPECS_ROOT = WORK / FEATURES_DIR
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = "test-feature"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".state"

pass_count = 0
fail_count = 0


def ok(name):
    global pass_count
    pass_count += 1
    print(f"PASS: {name}", flush=True)


def bad(name, detail=""):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
    if detail:
        msg += f" :: {detail}"
    print(msg, flush=True)


def reset_feature():
    if SPECS.exists():
        shutil.rmtree(SPECS, ignore_errors=True)
    SPECS.mkdir(parents=True, exist_ok=True)
    SDIR.mkdir(parents=True, exist_ok=True)
    run_trace("init", F)


def run_trace(*args, input_text=None):
    cmd = [PY, str(TRACE), "-C", str(WORK)] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, input=input_text)
    return proc.returncode, proc.stdout, proc.stderr


def run_validate(stage="spec"):
    rc, out, err = run_trace("validate", "--json", "--stage", stage, F)
    try:
        return rc, json.loads(out)
    except json.JSONDecodeError:
        return rc, {"findings": [], "summary": {}}


def write_spec(content):
    (SPECS / "spec.md").write_text(content, encoding="utf-8")


def has_finding(data, check_id):
    return any(f["check"] == check_id for f in data.get("findings", []))


def finding_msg(data, check_id):
    for f in data.get("findings", []):
        if f["check"] == check_id:
            return f["message"]
    return ""


MINIMAL_SPEC = """---
orderspec:
  artifact: spec
  slug: "test-feature"
  feature_id: "FEAT-001-test-feature"
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: "test-model"
---

# Test Feature

## 2. Goal & Scope

### Success Criteria

- **SC-001**: Test success criterion.

## 4. Functional Requirements

- **REQ-001**: System MUST do something testable.

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Test journey (Priority: P1)
  **Covers**: REQ-001
  **Why this priority**: Core.
  **Independent Test**: Verify something.
  **Done when**: Something works.

  - **AC-001**: [Covers: REQ-001] **Given** a user, **When** an action, **Then** a result.

## 13. Open Questions

None.

## 14. Decisions

- **DEC-001**: Test decision.
  - **Affects**: `IF-001` (test)
  - **Rationale**: Test rationale.

## 15. Assumptions

- **ASM-001**: [default] Test assumption.

## 16. Changelog

| Date | Type | Change | IDs affected | Contract impact | Reason |
|------|------|--------|--------------|-----------------|--------|
| 2026-01-01 | Added | Initial spec | All | New | Initial |
"""


def add_uj(spec_text, n, priority="P1"):
    uj = f"""
- **UJ-{n:03d}**: Test journey {n} (Priority: {priority})
  **Covers**: REQ-001
  **Why this priority**: Core.
  **Independent Test**: Test {n}.
  **Done when**: {n} works.

  - **AC-{n:03d}**: [Covers: REQ-001] **Given** a user, **When** action {n}, **Then** result {n}.
"""
    return spec_text.replace(
        "## 13. Open Questions",
        uj + "\n## 13. Open Questions",
    )


# ── Tests ────────────────────────────────────────────────────────────────────

# 1. M31 negative: 3 P1 UJs → finding
reset_feature()
spec = MINIMAL_SPEC
spec = add_uj(spec, 2, "P1")
spec = add_uj(spec, 3, "P1")
write_spec(spec)
rc, data = run_validate()
if has_finding(data, "M31"):
    ok("M31 neg: 3 P1 UJs detected")
else:
    bad("M31 neg: 3 P1 UJs not detected", f"findings={[f['check'] for f in data.get('findings',[])]}")

# 2. M31 positive: 1 P1 + 1 P2 → no finding
reset_feature()
spec = MINIMAL_SPEC
spec = add_uj(spec, 2, "P2")
write_spec(spec)
rc, data = run_validate()
if not has_finding(data, "M31"):
    ok("M31 pos: 1 P1 + 1 P2 passes")
else:
    bad("M31 pos: false positive", finding_msg(data, "M31"))

# 3. M31 boundary: exactly 2 P1 → no finding
reset_feature()
spec = MINIMAL_SPEC
spec = add_uj(spec, 2, "P1")
write_spec(spec)
rc, data = run_validate()
if not has_finding(data, "M31"):
    ok("M31 boundary: exactly 2 P1 passes")
else:
    bad("M31 boundary: 2 P1 false positive", finding_msg(data, "M31"))

# 4. M32 negative: DEC missing Affects
reset_feature()
spec = MINIMAL_SPEC.replace("  - **Affects**: `IF-001` (test)\n", "")
write_spec(spec)
rc, data = run_validate()
m32_findings = [f for f in data.get("findings", []) if f["check"] == "M32"]
if any("Affects" in f["message"] for f in m32_findings):
    ok("M32 neg Affects: detected")
else:
    bad("M32 neg Affects: not detected", f"m32_findings={m32_findings}")

# 5. M32 negative: DEC missing Rationale
reset_feature()
spec = MINIMAL_SPEC.replace("  - **Rationale**: Test rationale.\n", "")
write_spec(spec)
rc, data = run_validate()
m32_findings = [f for f in data.get("findings", []) if f["check"] == "M32"]
if any("Rationale" in f["message"] for f in m32_findings):
    ok("M32 neg Rationale: detected")
else:
    bad("M32 neg Rationale: not detected", f"m32_findings={m32_findings}")

# 6. M32 positive: DEC with both → no finding
reset_feature()
write_spec(MINIMAL_SPEC)
rc, data = run_validate()
m32_findings = [f for f in data.get("findings", []) if f["check"] == "M32"]
if not m32_findings:
    ok("M32 pos: complete DEC passes")
else:
    bad("M32 pos: false positive", str(m32_findings))

# 7. M30 positive: deferred EDGE → no finding
reset_feature()
spec = MINIMAL_SPEC.replace(
    "## 13. Open Questions",
    "## 11. Edge Cases\n\n- **EDGE-001**: Concurrent update \u2192 deferred (architectural concern).\n\n## 13. Open Questions",
)
write_spec(spec)
rc, data = run_validate()
if not has_finding(data, "M30"):
    ok("M30 pos: deferred EDGE passes")
else:
    bad("M30 pos: false positive", finding_msg(data, "M30"))

# 8. M30 negative: uncovered EDGE without defer → finding
reset_feature()
spec = MINIMAL_SPEC.replace(
    "## 13. Open Questions",
    "## 11. Edge Cases\n\n- **EDGE-001**: Concurrent update causes conflict.\n\n## 13. Open Questions",
)
write_spec(spec)
rc, data = run_validate()
if has_finding(data, "M30"):
    ok("M30 neg: uncovered EDGE detected")
else:
    bad("M30 neg: not detected")

# 9. M1a negative: AC without inline Covers
reset_feature()
spec = MINIMAL_SPEC.replace(
    "  - **AC-001**: [Covers: REQ-001] **Given** a user, **When** an action, **Then** a result.",
    "  - **AC-001**: **Given** a user, **When** an action, **Then** a result.",
)
write_spec(spec)
rc, data = run_validate()
if has_finding(data, "M1a"):
    ok("M1a neg: AC without Covers detected")
else:
    bad("M1a neg: not detected")

# 10. M6 negative: unresolved Q marker
reset_feature()
spec = MINIMAL_SPEC.replace(
    "## 13. Open Questions\n\nNone.",
    "## 13. Open Questions\n\n- **Q-001**: [NEEDS CLARIFICATION] What happens on timeout?\n\nNone.",
)
write_spec(spec)
rc, data = run_validate()
if has_finding(data, "M6"):
    ok("M6 neg: unresolved Q detected")
else:
    bad("M6 neg: not detected")

# 11. validate --json output structure
reset_feature()
write_spec(MINIMAL_SPEC)
rc, data = run_validate()
required_keys = {"stage", "scope", "summary", "findings"}
if required_keys.issubset(data.keys()):
    ok("validate --json: output has required keys")
else:
    bad("validate --json: missing keys", f"got {set(data.keys())}")

summary_keys = data.get("summary", {})
required_summary = {"total", "critical", "high", "medium", "low", "exit_code"}
if required_summary.issubset(summary_keys.keys()):
    ok("validate --json: summary has required keys")
else:
    bad("validate --json: summary missing keys", f"got {set(summary_keys.keys())}")

# 12. validate-frontmatter on valid spec
reset_feature()
write_spec(MINIMAL_SPEC)
rc, out, err = run_trace("validate-frontmatter", "spec", str(SPECS / "spec.md"), "--json")
if rc == 0:
    ok("validate-frontmatter: valid frontmatter passes")
else:
    bad("validate-frontmatter: rejected", f"rc={rc} out={out[:300]}")


# Helper to write plan.md
def write_plan(content):
    (SPECS / "plan.md").write_text(content, encoding="utf-8")

# Helper to create a file in the repo
def create_repo_file(rel_path, content=""):
    full_path = WORK / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")

# 13. [DEL] tag supported when file exists
reset_feature()
write_spec(MINIMAL_SPEC)
create_repo_file("src/old-file.py", "# old")
write_plan("""# Plan

## Physical Project Structure

```pathmanifest
src/old-file.py    [DEL]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc == 0 and "OK" in out:
    ok("[DEL] supported: file exists")
else:
    bad("[DEL] supported: file exists", f"rc={rc} err={err}")

# 14. [DEL] tag fails when file missing
reset_feature()
write_spec(MINIMAL_SPEC)
write_plan("""# Plan

## Physical Project Structure

```pathmanifest
src/missing.py    [DEL]
```
""")
rc, out, err = run_trace("check-plan", F)
if rc != 0 and "[DEL]" in err:
    ok("[DEL] fails: file missing")
else:
    bad("[DEL] fails: file missing", f"rc={rc} err={err}")

# 15. put-mechanisms --json works
reset_feature()
write_spec(MINIMAL_SPEC)
run_trace("extract-spec-ids", F)
json_data = json.dumps([
    {
        "spec_id": "REQ-001",
        "coverage_kind": "direct",
        "mechanism": "Test mechanism",
        "primary_files": "src/test.py",
        "test_type": "unit"
    }
])
rc, out, err = run_trace("put-mechanisms", "--json", F, input_text=json_data)
if rc == 0 and "wrote" in out:
    ok("put-mechanisms --json: valid input works")
    mech_file = SDIR / "mechanisms.tsv"
    content = mech_file.read_text()
    if "REQ-001" in content and "Test mechanism" in content:
        ok("put-mechanisms --json: content correct")
    else:
        bad("put-mechanisms --json: content incorrect", content)
else:
    bad("put-mechanisms --json: valid input failed", f"rc={rc} err={err}")

# 16. put-mechanisms --json fails on missing field
reset_feature()
write_spec(MINIMAL_SPEC)
run_trace("extract-spec-ids", F)
json_data = json.dumps([
    {
        "spec_id": "REQ-001",
        "coverage_kind": "direct",
        "mechanism": "Test mechanism",
        "primary_files": "src/test.py"
    }
])
rc, out, err = run_trace("put-mechanisms", "--json", F, input_text=json_data)
if rc != 0:
    ok("put-mechanisms --json: invalid input rejected")
else:
    bad("put-mechanisms --json: invalid input accepted", out)

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
sys.exit(0 if fail_count == 0 else 1)
