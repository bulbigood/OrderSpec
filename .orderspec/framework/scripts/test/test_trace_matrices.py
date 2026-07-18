#!/usr/bin/env python3
"""test_trace_matrices.py — regression tests for matrix data quality in trace_validate.py.

Tests:
  1. covers_reqs must not contain IF-* IDs (only REQ-)
  2. IF matrix success/failure must contain HTTP codes, not full text
  3. IF matrix must preserve full text in success_full/failure_full
  4. categories must include inventory counts
  5. acs_trace_to_reqs must be true when at least one AC traces to REQ
  6. acs_trace_to_reqs must be false when no AC traces to REQ
"""

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

WORK = Path(tempfile.mkdtemp(prefix="orderspec-trace-mat-"))
sys.path.insert(0, str(SCRIPT_DIR.parent))
from common import FEATURES_DIR

SPECS_ROOT = WORK / FEATURES_DIR
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = "test-matrices"
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
        return rc, {"findings": [], "summary": {}, "matrices": {}}


def write_spec(content):
    (SPECS / "spec.md").write_text(content, encoding="utf-8")


# ── Spec with IF section for matrix testing ─────────────────────────────────

SPEC_WITH_IF = """---
orderspec:
  artifact: spec
  slug: "test-matrices"
  feature_id: "FEAT-001-test-matrices"
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

# Test Matrices

## 2. Goal & Scope

### Success Criteria

- **SC-001**: Test success criterion.

## 3. Glossary

| Term | Definition |
|------|------------|
| Test | Test definition |

## 4. Functional Requirements

- **REQ-001**: System MUST do something testable.

## 5. Non-Functional Requirements

- **NFR-001**: System SHOULD be fast.

## 9. Interface Contracts

### Interfaces

- **IF-001**: Create test entity.

  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Create Entity |
  | Address | POST /entities |
  | Actor | Authenticated user |
  | Input | EntityInput |
  | Success | Returns 201 with created entity object |
  | Failure | Returns 400 for validation errors, 401 for unauthenticated |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: Entity MUST have an identifier.

### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 \u00d7 ASM-001 | INV-001: must have ID; ASM-001: ID auto-generated | compatible | ASM-001 provides the mechanism |

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Test journey (Priority: P1)
  **Covers**: REQ-001, IF-001
  **Why this priority**: Core.
  **Independent Test**: Test.
  **Done when**: Works.

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** a user, **When** POST /entities, **Then** returns 201.
  - **AC-002**: [Covers: IF-001] **Given** no auth token, **When** POST /entities, **Then** returns 401.

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

# Variant: UJ with only AC covering IF (no REQ trace)
SPEC_NO_REQ_TRACE = SPEC_WITH_IF.replace(
    "  - **AC-001**: [Covers: REQ-001, IF-001] **Given** a user, **When** POST /entities, **Then** returns 201.\n"
    "  - **AC-002**: [Covers: IF-001] **Given** no auth token, **When** POST /entities, **Then** returns 401.",
    "  - **AC-001**: [Covers: IF-001] **Given** no auth token, **When** POST /entities, **Then** returns 401."
)


# ── Tests ────────────────────────────────────────────────────────────────────

# 1. covers_reqs must not contain IF-* IDs
reset_feature()
write_spec(SPEC_WITH_IF)
rc, data = run_validate()
uj_matrix = data.get("matrices", {}).get("uj_coverage", [])
if uj_matrix:
    uj1 = uj_matrix[0]
    covers = uj1.get("covers_reqs", [])
    has_if = any(r.startswith("IF-") for r in covers)
    has_req = any(r.startswith("REQ-") for r in covers)
    if not has_if and has_req:
        ok("covers_reqs: IF-* IDs filtered out, REQ-* retained")
    else:
        bad("covers_reqs: filtering failed", f"covers_reqs={covers}")
else:
    bad("covers_reqs: no UJ matrix returned")


# 2. IF matrix success must contain only HTTP codes
reset_feature()
write_spec(SPEC_WITH_IF)
rc, data = run_validate()
if_matrix = data.get("matrices", {}).get("if_coverage", [])
if if_matrix:
    if1 = if_matrix[0]
    success = if1.get("success", "")
    # Should be "201", not "Returns 201 with created entity object"
    if success.strip() == "201":
        ok("IF matrix success: extracted HTTP code only")
    else:
        bad("IF matrix success: expected '201'", f"got '{success}'")
else:
    bad("IF matrix: no IF coverage returned")


# 3. IF matrix failure must contain only HTTP codes (sorted)
if if_matrix:
    if1 = if_matrix[0]
    failure = if1.get("failure", "")
    # Should be "400, 401", not the full text
    if failure.strip() == "400, 401":
        ok("IF matrix failure: extracted HTTP codes only")
    else:
        bad("IF matrix failure: expected '400, 401'", f"got '{failure}'")
else:
    bad("IF matrix failure: no IF coverage returned")


# 4. IF matrix must preserve full text in success_full/failure_full
if if_matrix:
    if1 = if_matrix[0]
    success_full = if1.get("success_full", "")
    failure_full = if1.get("failure_full", "")
    if "Returns 201 with" in success_full and "Returns 400" in failure_full:
        ok("IF matrix: full text preserved in _full fields")
    else:
        bad("IF matrix: _full fields missing or incorrect", f"success_full='{success_full}' failure_full='{failure_full}'")
else:
    bad("IF matrix: no IF coverage returned for _full check")


# 5. categories must include inventory counts
reset_feature()
write_spec(SPEC_WITH_IF)
rc, data = run_validate()
cats = data.get("categories", {})
fr_cat = cats.get("Functional Requirements", "")
if fr_cat.startswith("present") and "1" in fr_cat and "REQ" in fr_cat:
    ok(f"categories: Functional Requirements enriched ('{fr_cat}')")
else:
    bad("categories: Functional Requirements not enriched", f"got '{fr_cat}'")

uj_cat = cats.get("Acceptance Criteria & User Journeys", "")
if uj_cat.startswith("present") and "1" in uj_cat and "UJ" in uj_cat and "AC" in uj_cat:
    ok(f"categories: UJ/AC enriched ('{uj_cat}')")
else:
    bad("categories: UJ/AC not enriched", f"got '{uj_cat}'")

if_cat = cats.get("Interface Contracts", "")
if if_cat.startswith("present") and "1" in if_cat and "IF" in if_cat:
    ok(f"categories: Interface Contracts enriched ('{if_cat}')")
else:
    bad("categories: Interface Contracts not enriched", f"got '{if_cat}'")


# 6. acs_trace_to_reqs must be true when at least one AC traces to REQ
reset_feature()
write_spec(SPEC_WITH_IF)
rc, data = run_validate()
uj_matrix = data.get("matrices", {}).get("uj_coverage", [])
if uj_matrix:
    uj1 = uj_matrix[0]
    traces = uj1.get("acs_trace_to_reqs")
    if traces is True:
        ok("acs_trace_to_reqs: true when at least one AC traces to REQ")
    else:
        bad("acs_trace_to_reqs: expected true", f"got {traces}")
else:
    bad("acs_trace_to_reqs: no UJ matrix returned")


# 7. acs_trace_to_reqs must be false when no AC traces to REQ
reset_feature()
write_spec(SPEC_NO_REQ_TRACE)
rc, data = run_validate()
uj_matrix = data.get("matrices", {}).get("uj_coverage", [])
if uj_matrix:
    uj1 = uj_matrix[0]
    traces = uj1.get("acs_trace_to_reqs")
    if traces is False:
        ok("acs_trace_to_reqs: false when no AC traces to REQ")
    else:
        bad("acs_trace_to_reqs: expected false", f"got {traces}")
else:
    bad("acs_trace_to_reqs: no UJ matrix returned for false case")


# 8. Non-HTTP IF: success/failure should fall back to full text
SPEC_NON_HTTP = SPEC_WITH_IF.replace(
    "  | Kind | HTTP endpoint |",
    "  | Kind | CLI command |"
).replace(
    "  | Success | Returns 201 with created entity object |",
    "  | Success | Command exits with code 0 |"
).replace(
    "  | Failure | Returns 400 for validation errors, 401 for unauthenticated |",
    "  | Failure | Command exits with non-zero code |"
)
reset_feature()
write_spec(SPEC_NON_HTTP)
rc, data = run_validate()
if_matrix = data.get("matrices", {}).get("if_coverage", [])
if if_matrix:
    if1 = if_matrix[0]
    success = if1.get("success", "")
    # No HTTP codes → should fall back to full text
    if "Command exits with code 0" in success:
        ok("IF matrix: non-HTTP fallback to full text works")
    else:
        bad("IF matrix: non-HTTP fallback failed", f"success='{success}'")
else:
    bad("IF matrix: no IF coverage returned for non-HTTP test")


# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
sys.exit(0 if fail_count == 0 else 1)
