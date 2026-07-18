#!/usr/bin/env python3
"""Regression tests for /order.code deterministic lifecycle preflight."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "code_workflow.py"


def run(root, *args):
    process = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=root,
        env={**os.environ, "ORDERSPEC_ROOT": str(root)},
        capture_output=True,
        text=True,
    )
    return process.returncode, json.loads(process.stdout)


with tempfile.TemporaryDirectory(prefix="orderspec-code-workflow-") as temp:
    root = Path(temp)
    state = root / ".orderspec" / "state"
    feature = root / ".orderspec" / "features" / "001-demo"
    state.mkdir(parents=True)
    feature.mkdir(parents=True)
    (state / "active-feature.json").write_text(json.dumps({
        "feature_id": "FEAT-001-demo",
        "feature_directory": ".orderspec/features/001-demo",
        "status": "planned",
    }), encoding="utf-8")
    (feature / "plan.md").write_text("# Plan\n", encoding="utf-8")

    rc, data = run(root, "preflight", "--mode", "LOCAL_ALL")
    assert rc == 2 and data["error"] == "missing_tasks" and data["route"] == "/order.tasks", data

    rc, data = run(root, "preflight", "--mode", "RESET")
    assert rc == 2 and data["error"] == "missing_tasks", data

    source = root / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (feature / "spec.md").write_text("# Contract\n", encoding="utf-8")
    (feature / "plan.md").write_text(
        "## Physical Project Structure\n\n```pathmanifest\nsrc/service.py [MOD]\n```\n",
        encoding="utf-8",
    )
    (feature / "tasks.md").write_text(
        "# Tasks\n\n"
        "**Format (STRICT — pipe-delimited, machine-parsed)**\n\n"
        "## Task Context (Machine-Readable)\n\n"
        "```task-context\n"
        '{"version":1,"tasks":{"T001":{"read":["src/service.py"],"target_state":"mod"}}}\n'
        "```\n\n---\n\n"
        "## Phase 1\n\n"
        "- [ ] T001 | src/service.py |  | update service\n",
        encoding="utf-8",
    )
    rc, data = run(root, "preflight", "--mode", "LOCAL_ALL")
    assert rc == 0 and data["action"] == "READY" and data["first_unchecked"] == "T001", data
    rc, data = run(
        root,
        "next",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
    )
    assert rc == 0 and data["action"] == "EXECUTE_TASK", data
    envelope = data["worker_envelopes"][0]
    assert envelope["protocol_version"] == 1, envelope
    assert envelope["task"]["task_context"]["write_paths"] == ["src/service.py"], envelope
    assert envelope["capabilities"]["network"] is False, envelope
    assert set(envelope) == {"protocol_version", "instructions", "capabilities", "result_schema", "task"}, envelope

    rc, attempt = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T001",
    )
    assert rc == 0 and attempt["action"] == "DISPATCH", attempt
    source.write_text("VALUE = 2\n", encoding="utf-8")
    result_path = root / attempt["results_file"]
    result_path.write_text(json.dumps({
        "task_id": "T001",
        "status": "SUCCESS",
        "changed_files": ["src/service.py"],
        "verification": {"status": "NOT_RUN", "evidence": "not required"},
        "deviation": None,
    }), encoding="utf-8")
    rc, finished = run(
        root,
        "attempt-finish",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        attempt["attempt_id"],
        "--results-file",
        str(result_path),
    )
    assert rc == 0 and finished["action"] == "READY_TO_VERIFY_AND_MARK", finished
    assert finished["observed_by_task"] == {"T001": ["src/service.py"]}, finished

    rc, premature_cleanup = run(
        root,
        "attempt-cleanup",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        attempt["attempt_id"],
    )
    assert rc == 2 and premature_cleanup["error"] == "attempt_not_marked", premature_cleanup
    assert (feature / ".state" / "code-attempts" / f"{attempt['attempt_id']}.json").is_file()

    rc, attempt = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T001",
    )
    assert rc == 0, attempt
    (root / "forbidden.txt").write_text("unexpected\n", encoding="utf-8")
    attempt_state_dir = feature / ".state" / "code-attempts"
    (attempt_state_dir / "worker-intrusion.txt").write_text("unexpected\n", encoding="utf-8")
    result_path = root / attempt["results_file"]
    result_path.write_text(json.dumps({
        "task_id": "T001",
        "status": "SUCCESS",
        "changed_files": [],
        "verification": {"status": "NOT_RUN", "evidence": "not required"},
        "deviation": None,
    }), encoding="utf-8")
    rc, rejected = run(
        root,
        "attempt-finish",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        attempt["attempt_id"],
        "--results-file",
        str(result_path),
    )
    assert rc == 2 and rejected["error"] == "attempt_changes_rejected", rejected
    assert "forbidden.txt" in rejected["unexpected_changed_paths"], rejected
    assert any(path.endswith("worker-intrusion.txt") for path in rejected["unexpected_changed_paths"]), rejected

    rejected_state = attempt_state_dir / f"{attempt['attempt_id']}.json"
    rejected_result = result_path
    assert rejected_state.is_file() and rejected_result.is_file()

    tasks_path = feature / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("- [ ] T001", "- [X] T001"),
        encoding="utf-8",
    )
    successful_state = attempt_state_dir / f"{finished['attempt_id']}.json"
    first_result_path = root / (
        json.loads(successful_state.read_text(encoding="utf-8"))["results_file"]
    )
    rc, cleaned = run(
        root,
        "attempt-cleanup",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        finished["attempt_id"],
    )
    assert rc == 0 and cleaned["action"] == "ATTEMPT_CLEANED", cleaned
    assert not successful_state.exists() and not first_result_path.exists()
    assert rejected_state.is_file() and rejected_result.is_file()

    rc, rejected_cleanup = run(
        root,
        "attempt-cleanup",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        attempt["attempt_id"],
    )
    assert rc == 2 and rejected_cleanup["error"] == "attempt_not_accepted", rejected_cleanup
    assert rejected_state.is_file() and rejected_result.is_file()

print("All code-workflow tests passed")
