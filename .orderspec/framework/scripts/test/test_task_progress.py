#!/usr/bin/env python3
"""Regression tests for task_progress.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "task_progress.py"


def run(*args: str, input_text: str | None = None) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=input_text,
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


with tempfile.TemporaryDirectory(prefix="orderspec-task-progress-") as temp:
    tasks = Path(temp) / "tasks.md"
    tasks.write_text(
        """# Tasks

## Phase 1

- [ ] T001 | src/example.py | REQ-001 | add implementation
- [ ] T002 | tests/test_example.py | AC-001 | run tests
- [ ] T003 | tests/test_example.py |  | GATE: run tests
- [ ] T004 | src/example.py |  | VERIFY: run lint
- [ ] T005 [P] | src/a.py | REQ-002 | add independent A
- [ ] T006 [P] | src/b.py | REQ-003 | add independent B
""",
        encoding="utf-8",
    )

    rc, data = run("validate", "--tasks", str(tasks))
    expect(rc == 0 and data["unchecked"] == 6 and data["first_unchecked"] == "T001", "validate reports task state")

    rc, data = run("assert-complete", "--tasks", str(tasks))
    expect(
        rc != 0
        and data["error"] == "tasks_incomplete"
        and data["first_unchecked"] == "T001"
        and data["required_action"].startswith("CONTINUE Step 9"),
        "completion guard rejects partial progress and orders continuation",
    )

    out_of_order = {
        "task_id": "T002",
        "status": "SUCCESS",
        "changed_files": ["tests/test_example.py"],
        "verification": {"status": "PASS", "evidence": "expected red state observed"},
        "deviation": None,
    }
    rc, data = run("mark", "--tasks", str(tasks), input_text=json.dumps(out_of_order))
    expect(
        rc != 0 and data.get("terminal") is True and data["error"] == "out_of_order_mark",
        "marker rejects skipping first unchecked task as terminal",
    )

    success = {
        "task_id": "T001",
        "status": "SUCCESS",
        "changed_files": ["src/example.py"],
        "verification": {"status": "NOT_RUN", "evidence": "file updated"},
        "deviation": None,
    }

    empty_change = dict(success, changed_files=[])
    rc, data = run("mark", "--tasks", str(tasks), input_text=json.dumps(empty_change))
    expect(
        rc != 0
        and "non-GATE task must report exactly its task path" in data["message"]
        and data.get("terminal") is True
        and "- [ ] T001" in tasks.read_text(encoding="utf-8"),
        "ordinary task with empty changed_files stays unchecked",
    )

    rc, data = run("mark", "--tasks", str(tasks), input_text=json.dumps(success))
    expect(rc == 0 and data["task_id"] == "T001", "mark accepts successful implementation task")
    expect("- [X] T001" in tasks.read_text(encoding="utf-8"), "mark writes uppercase X")

    bad_path = dict(success, task_id="T002", changed_files=["src/other.py"])
    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(bad_path))
    expect(rc != 0 and "- [ ] T002" in tasks.read_text(encoding="utf-8"), "forbidden changed path stays unchecked")

    no_verify = dict(success, task_id="T002", changed_files=["tests/test_example.py"])
    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(no_verify))
    expect(rc != 0 and "- [ ] T002" in tasks.read_text(encoding="utf-8"), "test task requires verification")

    test_success = dict(
        no_verify,
        verification={"status": "PASS", "evidence": "expected red state observed"},
    )
    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(test_success))
    expect(rc == 0 and "- [X] T002" in tasks.read_text(encoding="utf-8"), "verified test task marks in order")

    gate_success = dict(
        no_verify,
        task_id="T003",
        changed_files=[],
        verification={"status": "PASS", "evidence": "tests passed"},
    )

    gate_changed = dict(gate_success, changed_files=["tests/test_example.py"])
    rc, data = run("mark", "--tasks", str(tasks), input_text=json.dumps(gate_changed))
    expect(
        rc != 0
        and "GATE/VERIFY task must report no changed files" in data["message"]
        and "- [ ] T003" in tasks.read_text(encoding="utf-8"),
        "gate cannot hide file changes",
    )

    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(gate_success))
    expect(rc == 0 and "- [X] T003" in tasks.read_text(encoding="utf-8"), "gate task marks after pass evidence")

    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(gate_success))
    expect(rc != 0, "already completed task cannot be marked twice")

    verify_success = dict(
        gate_success,
        task_id="T004",
        changed_files=[],
        verification={"status": "PASS", "evidence": "lint passed"},
    )
    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(verify_success))
    expect(rc == 0 and "- [X] T004" in tasks.read_text(encoding="utf-8"), "VERIFY task marks with no file changes")

    parallel_second = dict(
        success,
        task_id="T006",
        changed_files=["src/b.py"],
    )
    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(parallel_second))
    expect(rc == 0 and "- [X] T006" in tasks.read_text(encoding="utf-8"), "completed parallel sibling may mark first")

    parallel_first = dict(
        success,
        task_id="T005",
        changed_files=["src/a.py"],
    )
    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(parallel_first))
    expect(rc == 0 and "- [X] T005" in tasks.read_text(encoding="utf-8"), "remaining parallel sibling marks afterward")

    rc, data = run("assert-complete", "--tasks", str(tasks))
    expect(rc == 0 and data["unchecked"] == 0, "completion guard accepts all tasks marked")

with tempfile.TemporaryDirectory(prefix="orderspec-task-reconcile-") as temp:
    tasks = Path(temp) / "tasks.md"
    tasks.write_text(
        "# Tasks\n\n## Phase 1\n\n"
        "- [ ] T001 | src/existing.py | REQ-001 | add implementation\n"
        "- [X] T002 | src/second.py | REQ-002 | second implementation\n",
        encoding="utf-8",
    )
    reconciliation = {
        "task_id": "T001",
        "status": "ALREADY_COMPLETE",
        "changed_files": [],
        "verification": {"status": "PASS", "evidence": "targeted test passed"},
        "observed_state": "required function and error branch are present",
        "deviation": None,
    }
    invalid_reconciliation = dict(reconciliation, observed_state="")
    rc, data = run(
        "reconcile", "--tasks", str(tasks), input_text=json.dumps(invalid_reconciliation)
    )
    expect(
        rc != 0 and data.get("terminal") is True and "- [ ] T001" in tasks.read_text(encoding="utf-8"),
        "reconcile rejects missing observed-state evidence",
    )
    current_attempt = tasks.parent / ".state" / "code-attempts" / "current.json"
    current_attempt.parent.mkdir(parents=True)
    current_attempt.write_text("{}\n", encoding="utf-8")
    rc, data = run("reconcile", "--tasks", str(tasks), input_text=json.dumps(reconciliation))
    expect(
        rc != 0
        and data["error"] == "reconciliation_during_attempt"
        and data["recovery"]["action"] == "RECOVER_CURRENT_ATTEMPT"
        and "attempt-recover" in data["recovery"]["command"],
        "reconcile rejects an open attempt with an exact recovery command",
    )
    current_attempt.unlink()
    rc, data = run("reconcile", "--tasks", str(tasks), input_text=json.dumps(reconciliation))
    expect(rc == 0 and data["transition"] == "reconciled", "reconcile marks pre-existing verified work")

with tempfile.TemporaryDirectory(prefix="orderspec-story-gate-") as temp:
    tasks = Path(temp) / "tasks.md"
    tasks.write_text(
        "# Tasks\n\n## Story 1\n\n"
        "- [ ] T001 [US1] | src/story.py | AC-001 | implement story\n",
        encoding="utf-8",
    )
    rc, data = run("validate", "--tasks", str(tasks))
    expect(
        rc != 0 and "must end with a [US1] @verify task" in data["message"],
        "story phase without executable verification is rejected",
    )
    tasks.write_text(
        tasks.read_text(encoding="utf-8")
        + "- [ ] T002 [US1] | @verify |  | VERIFY: run focused tests; assert AC-001; STOP on failure\n",
        encoding="utf-8",
    )
    rc, data = run("validate", "--tasks", str(tasks))
    expect(rc == 0 and data["unchecked"] == 2, "story phase executable verification is accepted")

with tempfile.TemporaryDirectory(prefix="orderspec-red-evidence-") as temp:
    tasks = Path(temp) / "tasks.md"
    tasks.write_text(
        "# Tasks\n\n## Tests\n\n"
        "- [ ] T001 | tests/story.py | AC-001 | expected red: test missing behavior\n",
        encoding="utf-8",
    )
    result = {
        "task_id": "T001", "status": "SUCCESS", "changed_files": ["tests/story.py"],
        "verification": {"status": "PASS", "evidence": "AC-001 failed as declared"},
        "deviation": None,
    }
    rc, data = run("mark", "--tasks", str(tasks), input_text=json.dumps(result))
    expect(rc != 0 and "expected_outcome FAIL" in data["message"], "red evidence cannot be generic PASS")
    result["verification"].update({"expected_outcome": "FAIL", "observed_outcome": "FAIL"})
    rc, _ = run("mark", "--tasks", str(tasks), input_text=json.dumps(result))
    expect(rc == 0, "red evidence records expected and observed failure")

print("All task-progress tests passed")
