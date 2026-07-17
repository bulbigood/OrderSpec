#!/usr/bin/env python3
"""Regression tests for mechanism test-topology validation."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
TRACE = SCRIPT_DIR.parent / "traceability.py"

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-topology-"))
FEATURE = "test-topology"
FEATURE_DIR = WORK / ".orderspec" / "features" / FEATURE

sys.path.insert(0, str(SCRIPT_DIR.parent))
from trace_constants import TAB  # noqa: E402


SPEC = """---
orderspec:
  artifact: spec
  feature_id: FEAT-001-test-topology
  slug: test-topology
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

# Test Topology

- **REQ-001**: System MUST support the operation.
- **NFR-001**: System MUST preserve the documented behavior.
- **AC-001**: [Covers: REQ-001] The operation returns the expected result.
- **UJ-001**: Operation journey (Priority: P1)
  Covers: REQ-001, AC-001
"""


def run_trace(*args, input_text=None):
    proc = subprocess.run(
        [PY, str(TRACE), "-C", str(WORK), *args],
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr


def reset_feature(manifest, mechanisms):
    if FEATURE_DIR.exists():
        shutil.rmtree(FEATURE_DIR)
    FEATURE_DIR.mkdir(parents=True)
    (FEATURE_DIR / "spec.md").write_text(SPEC, encoding="utf-8")
    run_trace("init", FEATURE)
    (FEATURE_DIR / "plan.md").write_text(
        "```pathmanifest\n" + manifest + "\n```\n",
        encoding="utf-8",
    )
    rows = "\n".join(mechanisms)
    rc, out, err = run_trace("put-mechanisms", FEATURE, input_text=rows + "\n")
    assert rc == 0, (out, err)


def validate_plan():
    rc, output, error = run_trace("validate", "--json", "--stage", "plan", FEATURE)
    assert not error, error
    return rc, json.loads(output)


def has_m37(data):
    return any(finding["check"] == "M37" for finding in data["findings"])


def test_missing_unit_path_is_blocked():
    reset_feature(
        "src/services/operation.py  [NEW]",
        [f"REQ-001{TAB}direct{TAB}operation{TAB}src/services/operation.py{TAB}unit"],
    )
    rc, data = validate_plan()
    assert rc == 1
    assert has_m37(data)
    assert "tests/unit/" in next(
        finding["message"] for finding in data["findings"] if finding["check"] == "M37"
    )


def test_present_unit_path_passes_topology():
    reset_feature(
        "src/services/operation.py  [NEW]\ntests/unit/operation.test.py  [NEW]",
        [f"REQ-001{TAB}direct{TAB}operation{TAB}src/services/operation.py{TAB}unit"],
    )
    rc, data = validate_plan()
    assert rc == 0
    assert not has_m37(data)


def test_missing_integration_path_is_blocked():
    reset_feature(
        "src/routes/operation.py  [NEW]",
        [f"REQ-001{TAB}direct{TAB}operation endpoint{TAB}src/routes/operation.py{TAB}integration"],
    )
    rc, data = validate_plan()
    assert rc == 1
    assert has_m37(data)
    assert "tests/integration/" in next(
        finding["message"] for finding in data["findings"] if finding["check"] == "M37"
    )


def test_present_integration_path_passes_topology():
    reset_feature(
        "src/routes/operation.py  [NEW]\ntests/integration/operation.test.py  [NEW]",
        [f"REQ-001{TAB}direct{TAB}operation endpoint{TAB}src/routes/operation.py{TAB}integration"],
    )
    rc, data = validate_plan()
    assert rc == 0
    assert not has_m37(data)


def test_delegated_mechanism_inherits_target_topology():
    reset_feature(
        "src/routes/operation.py  [NEW]\ntests/integration/operation.test.py  [NEW]",
        [
            f"REQ-001{TAB}direct{TAB}operation endpoint{TAB}src/routes/operation.py{TAB}integration",
            f"AC-001{TAB}delegated:REQ-001{TAB}acceptance evidence{TAB}src/routes/operation.py{TAB}unit",
        ],
    )
    rc, data = validate_plan()
    assert rc == 0
    assert not has_m37(data)


def test_documented_mechanism_does_not_require_test_path():
    reset_feature(
        "docs/operation.md  [NEW]",
        [f"NFR-001{TAB}documented{TAB}documented behavior{TAB}docs/operation.md{TAB}documented"],
    )
    rc, data = validate_plan()
    assert rc == 0
    assert not has_m37(data)


try:
    tests = [
        test_missing_unit_path_is_blocked,
        test_present_unit_path_passes_topology,
        test_missing_integration_path_is_blocked,
        test_present_integration_path_passes_topology,
        test_delegated_mechanism_inherits_target_topology,
        test_documented_mechanism_does_not_require_test_path,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}", flush=True)
finally:
    shutil.rmtree(WORK, ignore_errors=True)

print("PASS: test-topology regression suite", flush=True)
