#!/usr/bin/env python3
"""test-validate-grid-rows.py — regression for _extract_grid_rows.

Tests the bug fix where a data row without a proper header was silently
swallowed because "inv" in keywords matched "INV-001" in the cell text.
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

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-grid-"))
sys.path.insert(0, str(SCRIPT_DIR.parent))

from trace_parse import _extract_grid_rows, _extract_section, ID_RE

from common import FEATURES_DIR
SPECS_ROOT = WORK / FEATURES_DIR
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = f".test-grid-{os.getpid()}"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".state"


def check_rows(rows, expected):
    if len(rows) != len(expected):
        return False
    for r, e in zip(rows, expected):
        if r.get("left_id") != e[0] or r.get("right_id") != e[1]:
            return False
    return True

pass_count = 0
fail_count = 0

def ok(name):
    global pass_count
    pass_count += 1
    print(f"PASS: {name}", flush=True)

def no(name, detail=""):
    global fail_count
    fail_count += 1
    print(f"FAIL: {name} :: {detail}", flush=True)

def reset_feature():
    if SPECS.exists():
        shutil.rmtree(SPECS, ignore_errors=True)
    SPECS.mkdir(parents=True, exist_ok=True)
    SDIR.mkdir(parents=True, exist_ok=True)
    (SDIR / ".schema").write_text("v1\n", encoding="utf-8")
    (SPECS / "spec.md").write_text("", encoding="utf-8")

def run_trace(*args):
    cmd = [PY, str(TRACE), "-C", str(WORK)] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr

def run_validate_json():
    rc, out, err = run_trace("validate", "--stage", "spec", "--json", F)
    if rc not in (0, 1):
        return rc, {}
    try:
        return rc, json.loads(out)
    except json.JSONDecodeError:
        return rc, {}

def has_finding(findings, check_id, message_contains=None):
    for f in findings:
        if f.get("check") == check_id:
            if message_contains is None or message_contains in f.get("message", ""):
                return True
    return False

print("\n=== Unit Tests: _extract_grid_rows ===\n")

# 1. Standard table with header + separator + data row
section = """### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", "NFR-001")]):
    ok("standard table: header + separator + 1 data row → 1 pair extracted")
else:
    no("standard table", f"expected [('INV-001','NFR-001')], got {rows}")

# 2. BUG SCENARIO: data row WITHOUT header (the bug)
# Old code: "inv" in keywords matched "INV-001" → data row treated as header → swallowed
# New code: ID pattern excluded from header detection → data row parsed as data
section = """### Contradiction Grid

| INV-001 × NFR-001 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", "NFR-001")]):
    ok("BUG FIX: data row without header → pair extracted (was swallowed before)")
else:
    no("bug fix no header", f"expected [('INV-001','NFR-001')], got {rows}")

# 3. Multiple data rows without header
section = """### Contradiction Grid

| INV-001 × NFR-001 | test | test | compatible |
| INV-002 × NFR-002 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", "NFR-001"), ("INV-002", "NFR-002")]):
    ok("multiple data rows without header → all pairs extracted")
else:
    no("multi no header", f"expected 2 pairs, got {rows}")

# 4. Table with header containing "invariant" (full word)
section = """### Contradiction Grid

| Invariant | NFR | Tension | Verdict |
|-----------|-----|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", "NFR-001")]):
    ok("header with 'Invariant' word → header detected, data row extracted")
else:
    no("header invariant word", f"expected [('INV-001','NFR-001')], got {rows}")

# 5. Table with header containing "pair"
section = """### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |
| INV-002 × ASM-001 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", "NFR-001"), ("INV-002", "ASM-001")]):
    ok("header with 'pair' → 2 data rows extracted")
else:
    no("header pair", f"expected 2 pairs, got {rows}")

# 6. Left ID only (no × separator, no right ID)
section = """### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", None)]):
    ok("left ID only → pair with right_id=None")
else:
    no("left only", f"expected [('INV-001',None)], got {rows}")

# 7. Empty grid (no table at all)
section = """### Contradiction Grid

No absolute INV × weakening NFR/ASM pairs.
"""
rows = _extract_grid_rows(section)
if check_rows(rows, []):
    ok("empty grid (no table) → 0 rows")
else:
    no("empty grid", f"expected [], got {rows}")

# 8. Grid with text "No pairs" and then a real table
section = """### Contradiction Grid

No pairs.

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", "NFR-001")]):
    ok("text 'No pairs' followed by table → table parsed")
else:
    no("no pairs + table", f"expected [('INV-001','NFR-001')], got {rows}")

# 9. REQ × ASM pair
section = """### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| REQ-001 × ASM-001 | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("REQ-001", "ASM-001")]):
    ok("REQ × ASM pair extracted")
else:
    no("req x asm", f"expected [('REQ-001','ASM-001')], got {rows}")

# 10. Table with extra whitespace
section = """### Contradiction Grid

|  Pair  |  Source  |  Tension  |  Verdict  |
|--------|----------|-----------|-----------|
|   INV-001 × NFR-001   |   test   |   test   |   compatible   |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, [("INV-001", "NFR-001")]):
    ok("table with extra whitespace → pair extracted")
else:
    no("extra whitespace", f"expected [('INV-001','NFR-001')], got {rows}")

# 11. Data row with no IDs (should not produce a pair)
section = """### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| some text | test | test | compatible |
"""
rows = _extract_grid_rows(section)
if check_rows(rows, []):
    ok("data row with no IDs → no pair extracted")
else:
    no("no ids", f"expected [], got {rows}")

print("\n=== Integration Tests: M24 with _extract_grid_rows ===\n")

reset_feature()

# 12. Absolute INV with proper grid → no M24
spec = """---
orderspec:
  artifact: spec
  slug: test-grid
  feature_id: FEAT-001-test-grid
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

# Test

## 4. Functional Requirements

- **REQ-001**: System MUST work.

## 9. Interface Contracts

- **IF-001**: Test.

  | Field | Value |
  |-------|-------|
  | Kind | HTTP endpoint |
  | Operation | Test |
  | Actor | User |
  | Success | 200 ok |
  | Failure | 400 error |
  | Covers | REQ-001 |

## 10. Invariants

- **INV-001**: System MUST have exactly one owner.

### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |

## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Test (Priority: P1)
  **Covers**: REQ-001, IF-001

  - **AC-001**: [Covers: REQ-001, IF-001] **Given** user, **When** test, **Then** 200 response.
  - **AC-002**: [Covers: REQ-001, IF-001] **Given** bad, **When** test, **Then** 400 response.
"""

(SPECS / "spec.md").write_text(spec, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()
findings = result.get("findings", [])

if not has_finding(findings, "M24"):
    ok("absolute INV with proper grid (header+separator+data) → no M24")
else:
    no("M24 proper grid", f"unexpected M24: {findings}")

# 13. Absolute INV with grid WITHOUT header (the bug scenario)
reset_feature()
spec_no_header = spec.replace(
    "| Pair | Source | Tension | Verdict |\n|------|--------|---------|---------|\n",
    ""
)
(SPECS / "spec.md").write_text(spec_no_header, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()
findings = result.get("findings", [])

if not has_finding(findings, "M24"):
    ok("BUG FIX: absolute INV with grid WITHOUT header → no M24 (data row now parsed)")
else:
    no("M24 no header", f"unexpected M24 (data row should be parsed now): {findings}")

# 14. Absolute INV with NO grid at all → M24
reset_feature()
spec_no_grid = spec.replace(
    """### Contradiction Grid

| Pair | Source | Tension | Verdict |
|------|--------|---------|---------|
| INV-001 × NFR-001 | test | test | compatible |""",
    """### Contradiction Grid

No rows."""
)
(SPECS / "spec.md").write_text(spec_no_grid, encoding="utf-8")
run_trace("extract-spec-ids", F)
rc, result = run_validate_json()
findings = result.get("findings", [])

if has_finding(findings, "M24", "INV-001"):
    ok("absolute INV with NO grid → M24 finding")
else:
    no("M24 no grid", f"expected M24 for INV-001, got: {findings}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
sys.exit(0 if fail_count == 0 else 1)
