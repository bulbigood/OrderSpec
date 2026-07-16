#!/usr/bin/env python3
"""Regression tests for task_contract_context.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "task_contract_context.py"


def run(root: Path, *args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=root,
        env={**os.environ, "ORDERSPEC_ROOT": str(root)},
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid JSON: {result.stdout!r}; stderr={result.stderr!r}") from exc
    return result.returncode, payload


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


with tempfile.TemporaryDirectory(prefix="orderspec-task-contract-context-") as temp:
    root = Path(temp)
    feature = root / ".orderspec" / "features" / "001-demo"
    state = feature / ".state"
    state.mkdir(parents=True)
    (root / ".orderspec").mkdir(exist_ok=True)

    (feature / "spec.md").write_text(
        "# Spec\n\n"
        "## Requirements\n\n"
        "- **REQ-001**: Task MUST keep its owner.\n"
        "  - **Verification**: owner stays unchanged.\n"
        "- **AC-001**: API returns the task owner.\n",
        encoding="utf-8",
    )
    (feature / "tasks.md").write_text(
        "# Tasks\n\n"
        "## Phase 1: Migrate\n\n"
        "**Goal**: Preserve ownership.\n\n"
        "**Verification**: Run focused tests.\n\n"
        "- [ ] T001 | src/task.js | REQ-001,AC-001 | implement ownership\n",
        encoding="utf-8",
    )
    (state / "mechanisms.tsv").write_text(
        "#orderspec mechanisms v1\n"
        "spec_id\tcoverage_kind\tmechanism\tprimary_files\ttest_type\n"
        "REQ-001\tdirect\towner field\tsrc/task.js\tunit\n"
        "AC-001\tdirect\towner response\ttests/task.test.js\tintegration\n",
        encoding="utf-8",
    )

    rc, data = run(root, "resolve", "--feature-dir", str(feature), "--task-id", "T001")
    expect(rc == 0 and data["ok"] is True, "resolve accepts task contract context")
    expect(data["refs"] == ["REQ-001", "AC-001"], "resolve extracts task spec IDs")
    expect(
        [item["id"] for item in data["spec_excerpts"]] == ["REQ-001", "AC-001"],
        "resolve returns exact spec excerpts in ref order",
    )
    expect(len(data["mechanisms"]) == 2, "resolve returns mechanism rows for task refs")
    expect(
        data["phase_context"] == ["**Goal**: Preserve ownership.", "**Verification**: Run focused tests."],
        "resolve returns current phase Goal and Verification",
    )

    (state / "mechanisms.tsv").write_text(
        "#orderspec mechanisms v1\n"
        "spec_id\tcoverage_kind\tmechanism\tprimary_files\ttest_type\n"
        "REQ-001\tdirect\towner field\tsrc/task.js\tunit\n",
        encoding="utf-8",
    )
    rc, data = run(root, "resolve", "--feature-dir", str(feature), "--task-id", "T001")
    expect(rc != 0 and data["error"] == "missing_mechanisms", "missing mechanism row blocks resolution")

    (feature / "tasks.md").write_text(
        "# Tasks\n\n"
        "## Phase 1: Migrate\n\n"
        "- [ ] T001 | src/task.js | REQ-999 | invalid reference\n",
        encoding="utf-8",
    )
    rc, data = run(root, "resolve", "--feature-dir", str(feature), "--task-id", "T001")
    expect(rc != 0 and data["error"] == "missing_spec_ids", "undefined spec ID blocks resolution")

    (feature / "spec.md").write_text(
        "# Spec\n\n- **REQ-001**: Task MUST keep its owner.\n",
        encoding="utf-8",
    )
    (feature / "tasks.md").write_text(
        "# Tasks\n\n## Phase 1: Migrate\n\n"
        "- [ ] T001 [US1] | src/task.js | REQ-001 | implement ownership\n",
        encoding="utf-8",
    )
    rc, data = run(root, "resolve", "--feature-dir", str(feature), "--task-id", "T001")
    expect(rc != 0 and data["error"] == "missing_phase_context", "story task requires phase context")

print("All task-contract-context tests passed")
