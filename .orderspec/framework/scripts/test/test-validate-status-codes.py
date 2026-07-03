#!/usr/bin/env python3
"""test-validate-status-codes.py — regression for _extract_status_codes and M29.

Tests:
1. _extract_status_codes: per-clause context (not per-line)
2. M19: AC→IF status cross-check
3. M29: IF→AC status coverage (new check)
4. Integration: full validate with spec containing IF/AC status mismatches
"""

import os
import shutil
import subprocess
import sys
import tempfile
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
TRACE = SCRIPT_DIR.parent / "traceability.py"

if not TRACE.exists():
    print(f"FATAL: traceability.py not found at {TRACE}", file=sys.stderr)
    sys.exit(2)

LOG_TO_FILE = False
TEST_DIR_LOCAL = SCRIPT_DIR / "test"
TEST_DIR_LOCAL.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR_LOCAL / "test-validate-status-codes.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-status-"))
sys.path.insert(0, str(SCRIPT_DIR.parent))

# Import _extract_status_codes directly for unit tests
from trace_parse import _extract_status_codes

# Setup feature dir
from common import FEATURES_DIR
SPECS_ROOT = WORK / FEATURES_DIR
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-status-{os.getpid()}"
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

def reset_feature():
    if SPECS.exists():
        shutil.rmtree(SPECS, ignore_errors=True)
    SPECS.mkdir(parents=True, exist_ok=True)
    SDIR.mkdir(parents=True, exist_ok=True)
    (SDIR / ".schema").write_text("v1\n", encoding="utf-8")
    (SPECS / "spec.md").write_text("", encoding="utf-8")

def run_trace(*args, input_text=None):
    cmd = [PY, str(TRACE), "-C", str(WORK)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr

def run_validate_json():
    rc, out, err = run_trace("validate", "--stage", "spec", "--json", F)
    if rc not in (0, 1):
        return rc, {}
    try:
        return rc, json.loads(out)
    except json.JSONDecodeError:
        return rc, {}

def find_finding(findings, check_id, message_contains=None):
    """Find a finding by check ID and optional message substring."""
    for f in findings:
        if f.get("check") == check_id:
            if message_contains is None or message_contains in f.get("message", ""):
                return f
    return None

def has_finding(findings, check_id, message_contains=None):
    return find_finding(findings, check_id, message_contains) is not None

# ── Unit Tests: _extract_status_codes ────────────────────────────────────────

print("\n=== Unit Tests: _extract_status_codes ===\n")

# 1. Single status with keyword
result = _extract_status_codes("200 OK")
if "200" in result:
    ok("single status with keyword 'OK'")
else:
    no("single status", f"got {result}")

# 2. Multiple statuses in separate clauses
result = _extract_status_codes("400 validation error; 403 forbidden; 404 not found")
if result == {"400", "403", "404"}:
    ok("multiple statuses in separate clauses — all extracted")
else:
    no("multiple clauses", f"expected {{400,403,404}}, got {result}")

# 3. CRITICAL: per-clause isolation — keyword in one clause should NOT validate status in another
result = _extract_status_codes("400 validation error; 403 not owner")
if "403" not in result and "400" in result:
    ok("per-clause isolation: 'error' in clause 1 does NOT validate 403 in clause 2")
else:
    no("per-clause isolation", f"expected 403 NOT extracted, got {result}")

# 4. Status without keyword in same clause
result = _extract_status_codes("403 not owner")
if "403" not in result:
    ok("status without keyword in clause — NOT extracted")
else:
    no("no keyword", f"expected 403 NOT extracted, got {result}")

# 5. Status with 'unauthenticated' (added to keywords)
result = _extract_status_codes("401 unauthenticated")
if "401" in result:
    ok("'unauthenticated' keyword recognized for 401")
else:
    no("unauthenticated", f"expected 401 extracted, got {result}")

# 6. Markdown table cell context
result = _extract_status_codes("200 OK — returned with task | 401 unauthorized | 403 forbidden")
if "200" in result and "401" in result and "403" in result:
    ok("markdown table cells: all statuses extracted from pipe-separated clauses")
else:
    no("table cells", f"expected {{200,401,403}}, got {result}")

# 7. Keyword in adjacent line should NOT validate status (old bug)
# Old behavior: context included adjacent lines, so keyword on line 1 validated status on line 2
text = "some error description\n403 status code here"
result = _extract_status_codes(text)
# "error" is on line 1, "403" is on line 2, "status" is on line 2
# With per-clause: line 1 has "error" but no status; line 2 has "403" and "status"
if "403" in result:
    ok("adjacent line: status extracted because its own line has keyword 'status'")
else:
    no("adjacent line", f"expected 403 extracted (has 'status' on same line), got {result}")

# 8. Adjacent line keyword does NOT leak (the old bug)
text = "validation error\n403 returned"
result = _extract_status_codes(text)
# "error" on line 1, "403" on line 2 with "returned"
# "returned" IS a keyword, so 403 should be extracted
if "403" in result:
    ok("adjacent line: 403 extracted because 'returned' is on same line")
else:
    no("adjacent returned", f"expected 403 extracted, got {result}")

# 9. No keyword at all
result = _extract_status_codes("403 404 500")
if result == set():
    ok("no keywords — nothing extracted")
else:
    no("no keywords", f"expected empty set, got {result}")

# 10. Invalid status codes ignored
result = _extract_status_codes("600 not found; 700 error; 200 ok")
if result == {"200"}:
    ok("invalid status codes (600, 700) ignored")
else:
    no("invalid codes", f"expected {{200}}, got {result}")

# 11. Empty text
result = _extract_status_codes("")
if result == set():
    ok("empty text — empty set")
else:
    no("empty", f"expected empty set, got {result}")

# 12. Newline-separated clauses
result = _extract_status_codes("200 success\n403 forbidden\n404 not found")
if result == {"200", "403", "404"}:
    ok("newline-separated clauses — all extracted")
else:
    no("newline clauses", f"expected {{200,403,404}}, got {result}")

# 13. Mixed separators
result = _extract_status_codes("200 ok; 403 forbidden\n404 not found")
if result == {"200", "403", "404"}:
    ok("mixed separators (; and newline) — all extracted")
else:
    no("mixed separators", f"expected {{200,403,404}}, got {result}")

# ── Integration Tests: M19 and M29 ───────────────────────────────────────────

print("\n=== Integration Tests: M19 and M29 ===\n")

reset_feature()

# 14. Spec with matching AC↔IF statuses — no findings
spec_content = """---
orderspec:
  artifact: spec
  slug: test-status
  feature_id: FEAT-001-test-status
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: test
---

# Test Spec

## 4. Functional Requirements

- **REQ-001**: System MUST create tasks.

## 9. Interface Contracts

- **IF-001**: Create Task.

  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Create |
  | Actor | User |
  | Success | 201 Created |
  | Failure | 400 validation error |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: Tasks MUST have unique IDs.

### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Create (Priority: P1)
  **Covers**: REQ-001, IF-001

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** user, **When** POST, **Then** 201 response.
  - **AC-002**: [Covers: REQ-001, IF-001] **Given** invalid input, **When** POST, **Then** 400 response.
"""

(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

if not has_finding(result.get("findings", []), "M19") and not has_finding(result.get("findings", []), "M29"):
    ok("matching AC↔IF statuses — no M19/M29 findings")
else:
    findings = result.get("findings", [])
    m19 = [f for f in findings if f.get("check") == "M19"]
    m29 = [f for f in findings if f.get("check") == "M29"]
    no("matching statuses", f"M19={m19}, M29={m29}")

# 15. AC references status not in IF → M19 finding
reset_feature()
spec_content = spec_content.replace(
    "- **AC-001**: [Covers: REQ-001, IF-001] **Given** user, **When** POST, **Then** 201 response.",
    "- **AC-001**: [Covers: REQ-001, IF-001] **Given** user, **When** POST, **Then** 200 response."
)
(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

if has_finding(result.get("findings", []), "M19", "200"):
    ok("AC references 200 not in IF (IF has 201) → M19 finding")
else:
    no("M19 AC→IF", f"findings: {result.get('findings', [])}")

# 16. IF Success status not covered by any AC → M29 HIGH
reset_feature()
spec_content = """---
orderspec:
  artifact: spec
  slug: test-status
  feature_id: FEAT-001-test-status
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: test
---

# Test Spec

## 4. Functional Requirements

- **REQ-001**: System MUST create tasks.

## 9. Interface Contracts

- **IF-001**: Create Task.

  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Create |
  | Actor | User |
  | Success | 201 Created |
  | Failure | 400 validation error; 404 not found |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: Tasks MUST have unique IDs.

### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Create (Priority: P1)
  **Covers**: REQ-001, IF-001

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** user, **When** POST, **Then** 201 response.
"""
# Note: AC-001 only covers 201, but IF has 400 and 404 in Failure
# M29 should flag 400 and 404 as MEDIUM (failure not covered)

(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

findings = result.get("findings", [])

# 201 is covered by AC-001 → no M29 for 201
if not has_finding(findings, "M29", "201"):
    ok("IF Success 201 covered by AC → no M29 finding for 201")
else:
    no("M29 success covered", f"should not flag 201: {findings}")

# 400 is not covered by any AC → M29 MEDIUM
m29_400 = find_finding(findings, "M29", "400")
if m29_400 and m29_400.get("severity") == "MEDIUM":
    ok("IF Failure 400 not covered → M29 MEDIUM finding")
else:
    no("M29 failure 400", f"expected M29 MEDIUM for 400, got: {findings}")

# 404 is not covered by any AC → M29 MEDIUM
m29_404 = find_finding(findings, "M29", "404")
if m29_404 and m29_404.get("severity") == "MEDIUM":
    ok("IF Failure 404 not covered → M29 MEDIUM finding")
else:
    no("M29 failure 404", f"expected M29 MEDIUM for 404, got: {findings}")

# 17. IF Success status not covered by any AC → M29 HIGH
reset_feature()
spec_content = """---
orderspec:
  artifact: spec
  slug: test-status
  feature_id: FEAT-001-test-status
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: test
---

# Test Spec

## 4. Functional Requirements

- **REQ-001**: System MUST create tasks.

## 9. Interface Contracts

- **IF-001**: Create Task.

  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Create |
  | Actor | User |
  | Success | 201 Created |
  | Failure | 400 validation error |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: Tasks MUST have unique IDs.

### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Create (Priority: P1)
  **Covers**: REQ-001, IF-001

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** invalid input, **When** POST, **Then** 400 response.
"""
# AC-001 only covers 400, but IF Success has 201
# M29 should flag 201 as HIGH (success not covered)

(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

findings = result.get("findings", [])

m29_201 = find_finding(findings, "M29", "201")
if m29_201 and m29_201.get("severity") == "HIGH":
    ok("IF Success 201 not covered by any AC → M29 HIGH finding")
else:
    no("M29 success HIGH", f"expected M29 HIGH for 201, got: {findings}")

# 400 is covered by AC-001 → no M29 for 400
if not has_finding(findings, "M29", "400"):
    ok("IF Failure 400 covered by AC → no M29 finding for 400")
else:
    no("M29 failure covered", f"should not flag 400: {findings}")

# 18. M24: absolute INV without grid row → M24 finding
reset_feature()
spec_content = """---
orderspec:
  artifact: spec
  slug: test-status
  feature_id: FEAT-001-test-status
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: test
---

# Test Spec

## 4. Functional Requirements

- **REQ-001**: System MUST create tasks.

## 9. Interface Contracts

- **IF-001**: Create Task.

  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Create |
  | Actor | User |
  | Success | 201 Created |
  | Failure | 400 validation error |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: Every task MUST have exactly one owner.

### Contradiction Grid

No rows.

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Create (Priority: P1)
  **Covers**: REQ-001, IF-001

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** user, **When** POST, **Then** 201 response.
  - **AC-002**: [Covers: REQ-001, IF-001] **Given** invalid, **When** POST, **Then** 400 response.
"""

(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

findings = result.get("findings", [])

if has_finding(findings, "M24", "INV-001"):
    ok("absolute INV (MUST have exactly) without grid row → M24 finding")
else:
    no("M24 absolute", f"expected M24 for INV-001, got: {findings}")

# 19. M24: absolute INV WITH grid row → no M24 finding
reset_feature()
spec_content = spec_content.replace(
    "No rows.",
    "| Pair | Source | Tension | Verdict |\n|------|--------|---------|---------|\n| INV-001 × NFR-001 | test | test | compatible |"
)
(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

findings = result.get("findings", [])

if not has_finding(findings, "M24"):
    ok("absolute INV WITH grid row → no M24 finding")
else:
    no("M24 with row", f"should not flag M24: {findings}")

# 20. Per-clause isolation in real spec (the original bug scenario)
reset_feature()
spec_content = """---
orderspec:
  artifact: spec
  slug: test-status
  feature_id: FEAT-001-test-status
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: test
---

# Test Spec

## 4. Functional Requirements

- **REQ-001**: System MUST create tasks.

## 9. Interface Contracts

- **IF-001**: Create Task.

  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Create |
  | Actor | User |
  | Success | 201 Created |
  | Failure | 400 validation error; 401 unauthenticated; 403 not owner; 404 not found |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: Tasks MUST have unique IDs.

### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Create (Priority: P1)
  **Covers**: REQ-001, IF-001

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** user, **When** POST, **Then** 201 response.
  - **AC-002**: [Covers: REQ-001, IF-001] **Given** invalid, **When** POST, **Then** 400 response.
  - **AC-003**: [Covers: REQ-001, IF-001] **Given** unauthenticated, **When** POST, **Then** 401 response.
  - **AC-004**: [Covers: REQ-001, IF-001] **Given** not owner, **When** POST, **Then** 403 response.
  - **AC-005**: [Covers: REQ-001, IF-001] **Given** missing, **When** POST, **Then** 404 response.
"""

(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

findings = result.get("findings", [])

# All statuses are covered by ACs → no M29 findings
m29_findings = [f for f in findings if f.get("check") == "M29"]
if not m29_findings:
    ok("per-clause isolation: all 5 statuses (201,400,401,403,404) covered → no M29")
else:
    no("per-clause all covered", f"unexpected M29: {m29_findings}")

# 21. Per-clause isolation: 403 "not owner" NOT extracted from IF → AC 403 not matched → M19
# This tests the FIX: old code would extract 403 from IF because "error" was on same line
# New code: 403 "not owner" has no keyword → 403 not in IF statuses → AC 403 triggers M19
reset_feature()
# Use same spec but remove AC-004 (the one that tests 403)
spec_content_no_403_ac = spec_content.replace(
    "  - **AC-004**: [Covers: REQ-001, IF-001] **Given** not owner, **When** POST, **Then** 403 response.\n",
    ""
)
(SPECS / "spec.md").write_text(spec_content_no_403_ac, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

findings = result.get("findings", [])

# With per-clause: IF Failure "403 not owner" → 403 NOT extracted (no keyword)
# So 403 is not in IF statuses
# No AC references 403 anymore, so no M19 for 403
# But 403 IS in IF text, just not extracted → M29 should not flag it either
# This is the correct behavior: "not owner" is not a recognized keyword

# Check: no M19 for 403 (because no AC references 403)
m19_403 = find_finding(findings, "M19", "403")
if not m19_403:
    ok("per-clause: 403 not extracted from IF (no keyword), no AC references 403 → no M19")
else:
    no("per-clause 403 M19", f"unexpected M19 for 403: {m19_403}")

# Check: no M29 for 403 (because 403 was not extracted from IF)
m29_403 = find_finding(findings, "M29", "403")
if not m29_403:
    ok("per-clause: 403 not extracted from IF → no M29 for 403")
else:
    no("per-clause 403 M29", f"unexpected M29 for 403: {m29_403}")

# 22. Non-HTTP IF: no M19/M29 checks
reset_feature()
spec_content = """---
orderspec:
  artifact: spec
  slug: test-status
  feature_id: FEAT-001-test-status
  status: draft
  refs:
    framework_rules: ".orderspec/framework/orderspec-rules.md"
    constitution: "constitution.md"
    stack: "stack.md"
    architecture: "architecture.md"
    conventions: "conventions.md"
  generator:
    command: order.spec
    model: test
---

# Test Spec

## 4. Functional Requirements

- **REQ-001**: System MUST emit events.

## 9. Interface Contracts

- **IF-001**: Emit Event.

  | Field | Value |
  |-------|-------|
  | Kind | Event publication |
  | Operation | Emit |
  | Actor | System |
  | Success | Event published |
  | Failure | Event not published |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: Events MUST have unique IDs.

### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Emit (Priority: P1)
  **Covers**: REQ-001, IF-001

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** state, **When** action, **Then** event published.
"""

(SPECS / "spec.md").write_text(spec_content, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()

findings = result.get("findings", [])

if not has_finding(findings, "M19") and not has_finding(findings, "M29"):
    ok("non-HTTP IF (Event publication) → no M19/M29 checks")
else:
    no("non-HTTP IF", f"unexpected M19/M29: {findings}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
