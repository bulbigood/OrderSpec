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


def run_command(root, command):
    process = subprocess.run(
        command,
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
    (feature / "spec.md").write_text(
        "# Contract\n\n## 8. Information Model\n\n### Entity: Service\n",
        encoding="utf-8",
    )
    (feature / "plan.md").write_text(
        "## Physical Project Structure\n\n```pathmanifest\nsrc/service.py [MOD]\n```\n",
        encoding="utf-8",
    )
    (feature / "tasks.md").write_text(
        "# Tasks\n\n"
        "**Format (STRICT — pipe-delimited, machine-parsed)**\n\n"
        "## Task Context (Machine-Readable)\n\n"
        "```task-context\n"
        '{"version":1,"tasks":{'
        '"T001":{"read":["src/service.py"],"target_state":"mod"},'
        '"T002":{"read":["src/service.py"],"target_state":"mod"}}}\n'
        "```\n\n---\n\n"
        "## Phase 1\n\n"
        "- [ ] T001 | src/service.py |  | update service\n"
        "- [ ] T002 | src/service.py |  | verify inherited service behavior\n",
        encoding="utf-8",
    )
    rc, reset = run(root, "preflight", "--mode", "RESET")
    assert rc == 0 and reset["action"] == "RESET_APPLY", reset
    assert reset["terminal"] is False and reset["continuation_required"] is True, reset
    assert reset["final_response"]["permitted"] is False, reset
    assert reset["command"][-1] == "--apply", reset
    rc, invalid_model = run(root, "preflight", "--mode", "LOCAL_ALL")
    assert rc == 2 and invalid_model["error"] == "invalid_task_contract_context", invalid_model
    assert invalid_model["route"] == "/order.spec", invalid_model
    (feature / "spec.md").write_text(
        "# Contract\n\n## 8. Information Model\n\n### Entity ENT-001: Service\n",
        encoding="utf-8",
    )
    rc, data = run(root, "preflight", "--mode", "LOCAL_ALL")
    assert rc == 0 and data["action"] == "READY" and data["first_unchecked"] == "T001", data
    assert data["terminal"] is False and data["continuation_required"] is True, data
    assert data["final_response"]["permitted"] is False, data
    feedback_dir = feature / ".state" / "feedback"
    feedback_dir.mkdir(parents=True)
    feedback_path = feedback_dir / "FB-001.json"
    feedback_path.write_text(json.dumps({
        "version": 1, "id": "FB-001", "scope": "feature", "status": "open",
        "created_at": "2026-07-19T00:00:00Z", "source": "order.code",
        "target": "order.tasks", "category": "implementation_repair",
        "summary": "focused gate failed", "evidence": "AC-001 assertion failed",
        "location": "T002", "requested_change": "insert a correction task before T002",
        "recommended_command": "/order.tasks \"insert a correction task before T002\"",
    }), encoding="utf-8")
    rc, routed = run(root, "preflight", "--mode", "LOCAL_ALL")
    assert rc == 0 and routed["action"] == "ROUTE_EXISTING_FEEDBACK", routed
    assert Path(routed["route_feedback"]["feedback_file"]).resolve() == feedback_path.resolve(), routed
    assert routed["terminal"] is False and routed["final_response"]["permitted"] is False, routed
    feedback_path.unlink()
    rc, data = run(
        root,
        "next",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
    )
    assert rc == 0 and data["action"] == "EXECUTE_TASK", data
    assert data["terminal"] is False and data["continuation_required"] is True, data
    assert data["final_response"]["permitted"] is False, data
    assert "attempt-begin" in data["next_action"], data
    envelope = data["worker_envelopes"][0]
    assert envelope["protocol_version"] == 1, envelope
    assert envelope["task"]["task_context"]["write_paths"] == ["src/service.py"], envelope
    assert envelope["capabilities"]["network"] is False, envelope
    assert set(envelope) == {"protocol_version", "instructions", "capabilities", "result_schema", "task"}, envelope

    begin_command = [
        sys.executable, str(SCRIPT), "attempt-begin", "--mode", "LOCAL_ALL",
        "--feature-dir", str(feature), "--task-id", "T001",
    ]
    processes = [
        subprocess.Popen(
            begin_command,
            cwd=root,
            env={**os.environ, "ORDERSPEC_ROOT": str(root)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]
    concurrent = []
    for process in processes:
        stdout, _ = process.communicate()
        concurrent.append((process.returncode, json.loads(stdout)))
    assert all(rc == 0 for rc, _ in concurrent), concurrent
    assert sum(payload["action"] == "DISPATCH" for _, payload in concurrent) == 1, concurrent
    attempt = next(payload for _, payload in concurrent if payload["action"] == "DISPATCH")
    assert {payload["attempt_id"] for _, payload in concurrent} == {attempt["attempt_id"]}, concurrent
    assert attempt["terminal"] is False and attempt["continuation_required"] is True, attempt
    rc, resumed = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T001",
    )
    assert rc == 0 and resumed["action"] == "RESUME_ATTEMPT", resumed
    assert resumed["attempt_id"] == attempt["attempt_id"], resumed
    assert resumed["worker_envelopes"] == attempt["worker_envelopes"], resumed
    rc, open_boundary = run(
        root,
        "finish",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--outcome",
        "HALTED",
    )
    assert rc == 2 and open_boundary["error"] == "open_attempt_boundary", open_boundary
    assert open_boundary["boundary_recovery"]["action"] == "RECOVER_CURRENT_ATTEMPT", open_boundary
    assert "attempt-recover" in open_boundary["boundary_recovery"]["command"], open_boundary
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
    assert finished["terminal"] is False and finished["continuation_required"] is True, finished
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
    assert (feature / ".state" / "code-attempts" / "current.json").is_file()

    rc, pending = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T001",
    )
    assert rc == 2 and pending["error"] == "attempt_pending_mark", pending

    tasks_path = feature / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("- [ ] T001", "- [X] T001"),
        encoding="utf-8",
    )
    attempt_state_dir = feature / ".state" / "code-attempts"
    successful_state = attempt_state_dir / "current.json"
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
    assert cleaned["terminal"] is False and cleaned["continuation_required"] is True, cleaned
    assert not successful_state.exists() and not first_result_path.exists()

    rc, inherited_attempt = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T002",
    )
    assert rc == 0 and inherited_attempt["action"] == "DISPATCH", inherited_attempt
    inherited_result_path = root / inherited_attempt["results_file"]
    inherited_result_path.write_text(json.dumps({
        "task_id": "T002",
        "status": "SUCCESS",
        "changed_files": [],
        "verification": {"status": "PASS", "evidence": "inherited behavior verified"},
        "deviation": None,
    }), encoding="utf-8")
    rc, inherited = run(
        root,
        "attempt-finish",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        inherited_attempt["attempt_id"],
        "--results-file",
        str(inherited_result_path),
    )
    assert rc == 0 and inherited["action"] == "RECONCILE_PREEXISTING", inherited
    assert inherited["retry_sources"] == {}, inherited
    assert inherited["completed_predecessor_sources"] == {"T002": ["T001"]}, inherited
    rc, inherited_mark = run_command(root, inherited["reconciliation_commands"][0])
    assert rc == 0 and inherited_mark["transition"] == "reconciled", inherited_mark

    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8")
        .replace("- [X] T001", "- [ ] T001")
        .replace("- [X] T002", "- [ ] T002"),
        encoding="utf-8",
    )
    rc, unsupported_noop = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T001",
    )
    assert rc == 0 and unsupported_noop["action"] == "DISPATCH", unsupported_noop
    unsupported_result_path = root / unsupported_noop["results_file"]
    unsupported_result_path.write_text(json.dumps({
        "task_id": "T001",
        "status": "SUCCESS",
        "changed_files": [],
        "verification": {"status": "PASS", "evidence": "unrelated no-op verification"},
        "deviation": None,
    }), encoding="utf-8")
    rc, unsupported_rejection = run(
        root,
        "attempt-finish",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        unsupported_noop["attempt_id"],
        "--results-file",
        str(unsupported_result_path),
    )
    assert rc == 2 and unsupported_rejection["error"] == "attempt_changes_rejected", unsupported_rejection

    rc, failed_attempt = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T001",
    )
    assert rc == 0 and failed_attempt["action"] == "DISPATCH", failed_attempt
    source.write_text("VALUE = 3\n", encoding="utf-8")
    failed_result_path = root / failed_attempt["results_file"]
    failed_result_path.write_text(json.dumps({
        "task_id": "T001",
        "status": "BLOCKED",
        "changed_files": ["src/service.py"],
        "verification": {"status": "FAIL", "evidence": "transient command failure"},
        "deviation": "verification was interrupted",
    }), encoding="utf-8")
    rc, worker_failed = run(
        root,
        "attempt-finish",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        failed_attempt["attempt_id"],
        "--results-file",
        str(failed_result_path),
    )
    assert rc == 2 and worker_failed["error"] == "worker_failed", worker_failed

    rc, retry_attempt = run(
        root,
        "attempt-begin",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
        "--task-id",
        "T001",
    )
    assert rc == 0 and retry_attempt["action"] == "DISPATCH", retry_attempt
    retry_result_path = root / retry_attempt["results_file"]
    retry_result_path.write_text(json.dumps({
        "task_id": "T001",
        "status": "SUCCESS",
        "changed_files": [],
        "verification": {"status": "PASS", "evidence": "retry verification passed"},
        "deviation": None,
    }), encoding="utf-8")
    rc, reconciliation = run(
        root,
        "attempt-finish",
        "--feature-dir",
        str(feature),
        "--attempt-id",
        retry_attempt["attempt_id"],
        "--results-file",
        str(retry_result_path),
    )
    assert rc == 0 and reconciliation["action"] == "RECONCILE_PREEXISTING", reconciliation
    assert reconciliation["terminal"] is False, reconciliation
    assert reconciliation["continuation_required"] is True, reconciliation
    assert reconciliation["retry_sources"] == {"T001": failed_attempt["attempt_id"]}, reconciliation
    assert not (attempt_state_dir / "current.json").exists(), reconciliation
    retry_history = attempt_state_dir / "history" / f"{retry_attempt['attempt_id']}.json"
    assert retry_history.is_file(), reconciliation
    retry_state = json.loads(retry_history.read_text(encoding="utf-8"))
    assert retry_state["finish_status"] == "reconcile_candidate", retry_state
    assert len(reconciliation["reconciliation_commands"]) == 1, reconciliation
    rc, reconciled = run_command(root, reconciliation["reconciliation_commands"][0])
    assert rc == 0 and reconciled["transition"] == "reconciled", reconciled
    assert "- [X] T001" in tasks_path.read_text(encoding="utf-8")

    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("- [X] T001", "- [ ] T001"),
        encoding="utf-8",
    )
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
    (root / "forbidden.txt").write_text("unexpected\n", encoding="utf-8")
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
    assert rejected["operator_action"]["resume_command"] == "/order.code --resume", rejected
    assert rejected["operator_action"]["reset_command"] == "/order.code --reset", rejected
    assert rejected["diagnostics"]["attempt_state"].endswith(f"{attempt['attempt_id']}.json"), rejected

    rejected_state = attempt_state_dir / "history" / f"{attempt['attempt_id']}.json"
    rejected_result = result_path
    assert rejected_state.is_file() and rejected_result.is_file()
    assert not (attempt_state_dir / "current.json").exists()
    rc, recovered = run(root, "attempt-recover", "--feature-dir", str(feature))
    assert rc == 0 and recovered["action"] == "NO_OPEN_ATTEMPT", recovered

    rc, preview = run(root, "attempt-reset", "--feature-dir", str(feature))
    assert rc == 0 and preview["action"] == "RESET_PREVIEW", preview
    assert rejected_state.relative_to(root).as_posix() in preview["delete"], preview
    assert rejected_result.relative_to(root).as_posix() in preview["delete"], preview
    assert rejected_state.is_file() and rejected_result.is_file()
    rc, reset = run(root, "attempt-reset", "--feature-dir", str(feature), "--apply")
    assert rc == 0 and reset["action"] == "ATTEMPT_STATE_RESET", reset
    assert not attempt_state_dir.exists()

    attempt_state_dir.mkdir(parents=True)
    (attempt_state_dir / "current.json").write_text('{"version":2}\n', encoding="utf-8")
    rc, invalid = run(root, "attempt-recover", "--feature-dir", str(feature))
    assert rc == 2 and invalid["error"] == "invalid_attempt_inventory", invalid
    assert invalid["recovery"]["action"] == "RESET_PREVIEW", invalid
    assert "attempt-reset" in invalid["recovery"]["command"], invalid
    rc, reset = run(root, "attempt-reset", "--feature-dir", str(feature), "--apply")
    assert rc == 0 and not attempt_state_dir.exists(), reset

print("All code-workflow tests passed")
