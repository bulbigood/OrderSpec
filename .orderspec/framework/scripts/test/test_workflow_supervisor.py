#!/usr/bin/env python3
"""Regression tests for persistent workflow supervisor transitions."""

import json
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "workflow_supervisor.py"
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "templates" / "automation-config.json"


def run(root: Path, *args: str, stdin: str | None = None):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(root), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )
    return result.returncode, json.loads(result.stdout)


with tempfile.TemporaryDirectory(prefix="orderspec-supervisor-") as temp:
    root = Path(temp)
    feature = root / ".orderspec" / "features" / "FEAT-001-example"
    feature.mkdir(parents=True)
    config_path = root / ".orderspec" / "config" / "automation.json"
    config_path.parent.mkdir(parents=True)
    config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config["enabled"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")

    rc, result = run(
        root,
        "start",
        "--feature-dir", str(feature),
        "--command", "order.code-check",
        "--terminal-command", "order.plan-check",
    )
    assert rc == 0 and result["run"]["status"] == "RUNNING", result
    run_file = Path(result["run_file"])
    assert run_file.is_file() and run_file.parent == (feature / ".state" / "runs").resolve()
    rc, attached = run(
        root,
        "acquire",
        "--feature-dir", str(feature),
        "--command", "order.code-check",
        "--terminal-command", "order.plan-check",
    )
    assert rc == 0 and attached["action"] == "RESUME_RUN", attached
    assert Path(attached["run_file"]) == run_file, attached
    assert attached["next_action"]["command"] == "order.code-check", attached
    assert attached["next_action"]["arguments"] == "", attached
    assert attached["final_response"]["permitted"] is False, attached
    assert "operator_action" not in attached, attached
    rc, running_status = run(root, "status", "--run-file", str(run_file))
    assert rc == 0 and running_status["terminal"] is False, running_status
    assert running_status["next_action"] == {
        "action": "EXECUTE_CURRENT_COMMAND",
        "command": "order.code-check",
        "arguments": "",
    }, running_status
    rc, guarded = run(root, "guard-final", "--run-file", str(run_file))
    assert rc == 1 and guarded["action"] == "CONTINUE_REQUIRED", guarded
    assert guarded["terminal"] is False and guarded["final_response"]["permitted"] is False, guarded
    assert running_status["final_response"] == {
        "permitted": False,
        "reason": "NON_TERMINAL_WORKFLOW_STATE",
    }, running_status
    assert "operator_action" not in running_status, running_status
    rc, recovery_status = run(
        root, "status", "--run-file", str(run_file), "--operator-recovery"
    )
    assert rc == 0, recovery_status
    assert recovery_status["operator_action"]["recommended_command"] == "/order.code-check"

    route = {
        "version": 1,
        "id": "EVT-001",
        "kind": "ROUTE",
        "reason": "UPSTREAM_DEFECT",
        "source": "order.code-check",
        "target": "order.plan",
        "severity": "HIGH",
        "summary": "physical mapping is incomplete",
        "evidence": "code-report.md finding C1-deadbeef",
    }
    illegal_advance = {
        "version": 1,
        "id": "EVT-000",
        "kind": "ADVANCE",
        "reason": "STAGE_COMPLETE",
        "source": "order.code-check",
        "target": "order.plan",
    }
    rc, rejected = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(illegal_advance),
    )
    assert rc == 2 and "illegal ADVANCE" in rejected["error"], rejected
    rc, result = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(route),
    )
    assert rc == 0 and result["decision"]["decision"] == "AUTO_ROUTE", result
    assert result["run"]["current_command"] == "order.plan", result
    assert result["run"]["session_mode"] == "fresh", result
    assert result["run"]["route_count"] == 1, result
    assert result["terminal"] is False and result["continuation_required"] is True, result
    assert result["next_action"] == {
        "action": "EXECUTE_NEXT_COMMAND", "command": "order.plan", "arguments": "",
    }, result
    assert result["final_response"]["permitted"] is False, result
    assert "operator_action" not in result, result

    invalid_question = {
        "version": 1,
        "id": "EVT-002",
        "kind": "OPERATOR_INPUT",
        "reason": "DECISION_REQUIRED",
        "source": "order.plan",
        "summary": "two delivery strategies remain plausible",
        "interaction": {
            "id": "INT-001",
            "kind": "DECISION_REQUIRED",
            "question": "Keep the current interface or add a new one?",
            "options": ["keep", "add"],
            "choices": [
                {"value": "keep", "label": "Keep interface", "consequence": "Preserve the current interface."},
                {"value": "add", "label": "Add interface", "consequence": "Add the proposed interface."},
            ],
            "resume_strategy": "same_session"
        }
    }
    rc, rejected = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(invalid_question),
    )
    assert rc == 1 and rejected["error_code"] == "CALLER_EVENT_INVALID", rejected
    assert rejected["state_mutated"] is False, rejected
    assert rejected["allowed_values"]["reason"] == sorted([
        "SEMANTIC_DECISION", "SCOPE_CLARIFICATION", "MUTATION_APPROVAL",
        "TOOL_INSTALL_APPROVAL", "GOVERNANCE_APPROVAL", "CANDIDATE_SELECTION",
        "WORK_ORDER_RESET_REQUIRED", "CREDENTIALS_REQUIRED", "PERMISSION_REQUIRED",
    ]), rejected
    assert rejected["terminal"] is False and rejected["continuation_required"] is True, rejected
    assert rejected["final_response"]["permitted"] is False, rejected
    assert rejected["run"]["status"] == "RUNNING", rejected

    direct_question = {
        **invalid_question,
        "reason": "SEMANTIC_DECISION",
        "interaction": {
            **invalid_question["interaction"],
            "kind": "SEMANTIC_DECISION",
            "options": ["keep", "add"],
        },
    }
    rc, rejected = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(direct_question),
    )
    assert rc == 1 and rejected["error_code"] == "CALLER_EVENT_INVALID", rejected
    assert any("direct OPERATOR_INPUT is forbidden" in item for item in rejected["field_errors"]), rejected
    assert rejected["state_mutated"] is False and rejected["run"]["status"] == "RUNNING", rejected

    rc, rejected = run(
        root,
        "ask",
        "--run-file", str(run_file),
        "--source", "order.plan",
        "--reason", "DECISION_REQUIRED",
        "--interaction-id", "INT-001",
        "--question", "Keep the current interface or add a new one?",
        "--choice", "keep", "Keep interface", "Preserve the current interface.",
        "--choice", "add", "Add interface", "Add the proposed interface.",
    )
    assert rc == 1 and rejected["error_code"] == "CALLER_EVENT_INVALID", rejected
    assert "SEMANTIC_DECISION" in rejected["allowed_values"]["reason"], rejected
    assert rejected["state_mutated"] is False and rejected["run"]["status"] == "RUNNING", rejected

    rc, rejected = run(
        root,
        "ask",
        "--run-file", str(run_file),
        "--source", "order.plan",
        "--reason", "SEMANTIC_DECISION",
        "--interaction-id", "INT-001",
        "--question", "Keep the current interface or add a new one?",
        "--option", "keep",
        "--option", "add",
    )
    assert rc == 1 and rejected["error_code"] == "CALLER_EVENT_INVALID", rejected
    assert any("--option lacks operator-facing meaning" in item for item in rejected["field_errors"]), rejected
    assert rejected["state_mutated"] is False and rejected["run"]["status"] == "RUNNING", rejected

    rc, result = run(
        root,
        "ask",
        "--run-file", str(run_file),
        "--source", "order.plan",
        "--reason", "SEMANTIC_DECISION",
        "--interaction-id", "INT-001",
        "--question", "Keep the current interface or add a new one?",
        "--choice", "keep", "Keep interface", "Preserve the current interface.",
        "--choice", "add", "Add interface", "Add the proposed interface.",
        "--summary", "two delivery strategies remain plausible",
    )
    assert rc == 0 and result["run"]["status"] == "WAITING_OPERATOR", result
    assert result["run"]["pending_interaction"]["id"] == "INT-001", result
    assert result["operator_action"]["recommended_replies"] == ["keep", "add"], result
    assert [choice["value"] for choice in result["operator_action"]["choices"]] == ["keep", "add"], result
    assert result["operator_action"]["choices"][0]["consequence"] == "Preserve the current interface.", result
    assert result["operator_action"]["presentation"]["language"] == "user_configured", result
    assert result["operator_action"]["presentation"]["explain_each_choice"] is True, result
    assert [item["reply"] for item in result["operator_action"]["answer_commands"]] == [
        "keep", "add"
    ], result
    assert all("workflow_supervisor.py" in item["command"] for item in result["operator_action"]["answer_commands"]), result

    rc, rejected = run(
        root, "answer", "--run-file", str(run_file),
        "--interaction-id", "INT-001", "--answer", "unknown",
    )
    assert rc == 1 and rejected["error_code"] == "INVALID_OPERATOR_ANSWER", rejected
    assert rejected["state_mutated"] is False and rejected["terminal"] is True, rejected
    assert rejected["operator_action"]["recommended_replies"] == ["keep", "add"], rejected

    rc, result = run(
        root, "answer", "--run-file", str(run_file),
        "--interaction-id", "INT-001", "--answer", "keep",
    )
    assert rc == 0 and result["run"]["status"] == "RUNNING", result
    assert result["run"]["session_mode"] == "resume", result
    assert result["run"]["resume_input"]["answer"] == "keep", result
    assert result["terminal"] is False and result["continuation_required"] is True, result
    assert result["next_action"]["resume_input"]["answer"] == "keep", result
    assert result["final_response"]["permitted"] is False, result

    rc, result = run(
        root,
        "ask",
        "--run-file", str(run_file),
        "--source", "order.plan",
        "--reason", "SCOPE_CLARIFICATION",
        "--interaction-id", "INT-002",
        "--question", "Which bounded module owns this behavior?",
        "--response-type", "text",
    )
    assert rc == 0 and result["run"]["status"] == "WAITING_OPERATOR", result
    assert "answer_command_template" in result["operator_action"], result
    rc, result = run(
        root, "answer", "--run-file", str(run_file),
        "--interaction-id", "INT-002", "--answer", "src/billing",
    )
    assert rc == 0 and result["run"]["resume_input"]["answer"] == "src/billing", result

    rc, missing_source = run(
        root, "advance", "--run-file", str(run_file),
        "--summary", "plan stage completed",
    )
    assert rc == 1 and missing_source["action"] == "ADVANCE_SOURCE_REQUIRED", missing_source
    assert missing_source["next_action"]["command"] == "order.plan", missing_source

    rc, result = run(
        root, "advance", "--run-file", str(run_file),
        "--source", "order.plan",
        "--summary", "plan stage completed",
    )
    assert rc == 0 and result["run"]["current_command"] == "order.plan-check", result
    assert result["run"]["history"][-1]["event"]["source"] == "order.plan", result
    assert result["run"]["history"][-1]["event"]["target"] == "order.plan-check", result
    assert result["terminal"] is False and result["continuation_required"] is True, result
    assert result["next_action"] == {
        "action": "EXECUTE_NEXT_COMMAND", "command": "order.plan-check", "arguments": "",
    }, result
    assert result["final_response"]["permitted"] is False, result
    assert "operator_action" not in result, result

    rc, stale = run(
        root, "advance", "--run-file", str(run_file),
        "--source", "order.plan",
        "--summary", "duplicate stale completion",
    )
    assert rc == 1 and stale["action"] == "STALE_ADVANCE_REJECTED", stale
    assert stale["run"]["current_command"] == "order.plan-check", stale
    assert stale["next_action"]["command"] == "order.plan-check", stale

    plan_report = feature / "plan-report.md"
    plan_report.write_text(
        "---\norderspec:\n  artifact: gate_report\n  command: order.plan-check\n"
        "  verdict: PASS\n---\n",
        encoding="utf-8",
    )

    complete = {
        "version": 1,
        "id": "EVT-005",
        "kind": "COMPLETE",
        "reason": "WORKFLOW_COMPLETE",
        "source": "order.plan-check",
        "evidence": str(plan_report.relative_to(root)),
    }
    rc, result = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(complete),
    )
    assert rc == 0 and result["decision"]["decision"] == "COMPLETE", result
    assert result["run"]["status"] == "COMPLETE", result
    assert result["terminal"] is True and result["continuation_required"] is False, result

    rc, result = run(root, "status", "--run-file", str(run_file))
    assert rc == 0 and len(result["run"]["history"]) == 8, result

    config["enabled"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    rc, paused_run = run(
        root,
        "start",
        "--feature-dir", str(feature),
        "--command", "order.plan",
        "--terminal-command", "order.plan-check",
    )
    assert rc == 0, paused_run
    paused_file = Path(paused_run["run_file"])
    pause_event = {
        "version": 1,
        "id": "EVT-006",
        "kind": "ADVANCE",
        "reason": "STAGE_COMPLETE",
        "source": "order.plan",
        "target": "order.plan-check",
    }
    rc, paused = run(
        root, "evaluate", "--run-file", str(paused_file), "--event-file", "-",
        stdin=json.dumps(pause_event),
    )
    assert rc == 0 and paused["run"]["status"] == "PAUSED", paused
    assert paused["terminal"] is True and paused["continuation_required"] is False, paused
    assert "status_command" in paused["operator_action"], paused
    rc, acquired_pause = run(
        root,
        "acquire",
        "--feature-dir", str(feature),
        "--command", "order.plan",
        "--terminal-command", "order.plan-check",
    )
    assert rc == 0 and acquired_pause["action"] == "OPERATOR_BOUNDARY", acquired_pause
    assert Path(acquired_pause["run_file"]) == paused_file, acquired_pause
    rc, rejected = run(
        root, "evaluate", "--run-file", str(paused_file), "--event-file", "-",
        stdin=json.dumps(pause_event),
    )
    assert rc == 2 and "PAUSED" in rejected["error"], rejected
    rc, resumed = run(
        root, "resume", "--run-file", str(paused_file),
        "--reason", "operator reviewed the pause",
    )
    assert rc == 0 and resumed["run"]["status"] == "RUNNING", resumed
    assert resumed["run"]["current_command"] == "order.plan-check", resumed
    assert resumed["next_action"] == {
        "action": "EXECUTE_CURRENT_COMMAND", "command": "order.plan-check", "arguments": "",
    }, resumed
    assert resumed["final_response"]["permitted"] is False, resumed
    assert resumed["run"]["history"][-1]["type"] == "OPERATOR_RESUME", resumed
    assert resumed["run"]["history"][-1]["applied_transition"] == {
        "event_id": "EVT-006", "kind": "ADVANCE",
        "source": "order.plan", "target": "order.plan-check",
    }, resumed

    processes = [
        subprocess.Popen(
            [sys.executable, str(SCRIPT), "-C", str(root), "start", "--command", "order.spec"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(12)
    ]
    concurrent = [json.loads(process.communicate()[0]) for process in processes]
    concurrent_paths = [item["run_file"] for item in concurrent]
    assert len(concurrent_paths) == len(set(concurrent_paths)) == 12, concurrent_paths
    assert all(Path(path).is_file() for path in concurrent_paths), concurrent_paths

    acquire_feature = root / ".orderspec" / "features" / "FEAT-002-acquire"
    acquire_feature.mkdir(parents=True)
    acquire_processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(SCRIPT),
                "-C",
                str(root),
                "acquire",
                "--feature-dir",
                str(acquire_feature),
                "--command",
                "order.code",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(12)
    ]
    acquired = [json.loads(process.communicate()[0]) for process in acquire_processes]
    acquired_paths = {item["run_file"] for item in acquired}
    assert len(acquired_paths) == 1, acquired
    assert sum(item["action"] == "STARTED_RUN" for item in acquired) == 1, acquired
    assert sum(item["action"] == "RESUME_RUN" for item in acquired) == 11, acquired
    assert all(item["next_action"]["arguments"] == "--resume" for item in acquired), acquired

    stale_path = Path(next(iter(acquired_paths)))
    stale_state = json.loads(stale_path.read_text(encoding="utf-8"))
    stale_state["created_at"] = "2000-01-01T00:00:00Z"
    stale_path.write_text(json.dumps(stale_state), encoding="utf-8")
    rc, terminal_run = run(
        root,
        "start",
        "--feature-dir", str(acquire_feature),
        "--command", "order.code",
    )
    assert rc == 0, terminal_run
    terminal_path = Path(terminal_run["run_file"])
    terminal_state = json.loads(terminal_path.read_text(encoding="utf-8"))
    terminal_state["status"] = "COMPLETE"
    terminal_state["created_at"] = "2001-01-01T00:00:00Z"
    terminal_path.write_text(json.dumps(terminal_state), encoding="utf-8")
    rc, after_terminal = run(
        root,
        "acquire",
        "--feature-dir", str(acquire_feature),
        "--command", "order.code",
    )
    assert rc == 0 and after_terminal["action"] == "STARTED_RUN", after_terminal
    assert Path(after_terminal["run_file"]) not in {stale_path, terminal_path}, after_terminal
    assert str(stale_path) in after_terminal["superseded_active_runs"], after_terminal

    config["enabled"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")
    rc, code_run = run(
        root,
        "start",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0, code_run
    code_run_file = Path(code_run["run_file"])
    (feature / "tasks.md").write_text(
        "# Tasks\n\n## Phase 1\n\n- [ ] T001 | src/example.js |  | implement bounded task\n",
        encoding="utf-8",
    )
    rc, incomplete_advance = run(
        root, "advance", "--run-file", str(code_run_file), "--source", "order.code",
    )
    assert rc == 1 and incomplete_advance["action"] == "ORDER_CODE_INCOMPLETE", incomplete_advance
    assert incomplete_advance["run"]["current_command"] == "order.code", incomplete_advance
    assert incomplete_advance["next_action"] == {
        "action": "EXECUTE_CURRENT_COMMAND", "command": "order.code", "arguments": "--resume",
    }, incomplete_advance
    attempt_dir = feature / ".state" / "code-attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    attempt_id = "a" * 32
    envelope = {
        "protocol_version": 1,
        "instructions": ["execute"],
        "capabilities": {},
        "result_schema": {},
        "task": {
            "task_id": "T001", "phase": "Phase 1", "task_line": "T001", "objective": "test",
            "task_context": {"to_read": [], "write_paths": [], "target_state": "verify"},
            "contract_context": {}, "inline_context": [],
            "verification": {"required": False, "source": "task_line", "expected": "PASS"},
            "read_only": True, "stop_conditions": [],
        },
    }
    attempt_state = {
        "version": 3, "attempt_id": attempt_id, "mode": "LOCAL_ALL",
        "feature_dir": ".orderspec/features/001-demo", "task_ids": ["T001"],
        "write_paths": {"T001": []}, "verification_required": {"T001": False},
        "worker_envelopes": [envelope], "baseline": {},
        "results_file": f".orderspec/features/001-demo/.state/code-attempts/{attempt_id}-results.json",
    }
    attempt_state["state_digest"] = hashlib.sha256(
        json.dumps(attempt_state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    attempt_path = attempt_dir / "current.json"
    attempt_path.write_text(json.dumps(attempt_state), encoding="utf-8")
    code_route = {
        "version": 1,
        "id": "EVT-CODE-001",
        "kind": "ROUTE",
        "reason": "UPSTREAM_DEFECT",
        "source": "order.code",
        "target": "order.tasks",
        "severity": "HIGH",
        "summary": "task context is incomplete",
        "evidence": "FB-001",
    }
    rc, rejected = run(
        root, "evaluate", "--run-file", str(code_run_file), "--event-file", "-",
        stdin=json.dumps(code_route),
    )
    assert rc == 2 and "command boundary rejected" in rejected["error"], rejected
    persisted = json.loads(code_run_file.read_text(encoding="utf-8"))
    assert persisted["status"] == "RUNNING" and persisted["transition_count"] == 0, persisted

    history_dir = attempt_dir / "history"
    history_dir.mkdir()
    attempt_path.replace(history_dir / f"{attempt_id}.json")
    rc, routed = run(
        root, "evaluate", "--run-file", str(code_run_file), "--event-file", "-",
        stdin=json.dumps(code_route),
    )
    assert rc == 0 and routed["run"]["current_command"] == "order.tasks", routed

    rc, feedback_run = run(
        root,
        "start",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0, feedback_run
    feedback_file = feature / ".state" / "feedback" / "FB-001.json"
    feedback_file.parent.mkdir(parents=True, exist_ok=True)
    feedback_file.write_text(json.dumps({
        "version": 1,
        "id": "FB-001",
        "scope": "feature",
        "status": "open",
        "created_at": "2026-07-19T00:00:00Z",
        "source": "order.code",
        "target": "order.bootstrap",
        "category": "project_capability",
        "summary": "test execution is denied",
        "evidence": "T006 requires declared integration evidence",
        "location": ".orderspec/contracts/constitution.md",
        "requested_change": 'allow "focused" integration tests',
        "fingerprint": "abc",
        "recommended_command": "ignored legacy rendering",
    }), encoding="utf-8")
    rc, routed_feedback = run(
        root,
        "route-feedback",
        "--run-file", feedback_run["run_file"],
        "--feedback-file", str(feedback_file),
    )
    assert rc == 0 and routed_feedback["decision"]["decision"] == "AUTO_ROUTE", routed_feedback
    assert routed_feedback["run"]["current_command"] == "order.bootstrap", routed_feedback
    assert routed_feedback["next_action"] == {
        "action": "EXECUTE_OWNER_COMMAND",
        "command": "order.bootstrap",
        "arguments": 'allow "focused" integration tests',
        "recommended_command": '/order.bootstrap "allow \\"focused\\" integration tests"',
    }, routed_feedback
    assert routed_feedback["terminal"] is False, routed_feedback
    assert routed_feedback["continuation_required"] is True, routed_feedback
    assert routed_feedback["final_response"]["permitted"] is False, routed_feedback
    assert "operator_action" not in routed_feedback, routed_feedback
    assert set(routed_feedback["run"]["history"][-1]["event"]) == {
        "version", "id", "kind", "reason", "source", "target", "severity",
        "destructive", "summary", "evidence", "interaction",
    }, routed_feedback

    repair_run_rc, repair_run = run(
        root, "start", "--feature-dir", str(feature), "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert repair_run_rc == 0, repair_run
    repair_file = feedback_file.with_name("FB-002.json")
    repair_payload = json.loads(feedback_file.read_text(encoding="utf-8"))
    repair_payload.update({
        "id": "FB-002", "target": "order.tasks", "category": "implementation_repair",
        "requested_change": "insert bounded correction tasks before the failed gate",
    })
    repair_file.write_text(json.dumps(repair_payload), encoding="utf-8")
    rc, repair_route = run(
        root, "route-feedback", "--run-file", repair_run["run_file"],
        "--feedback-file", str(repair_file),
    )
    assert rc == 0, repair_route
    assert repair_route["run"]["history"][-1]["event"]["reason"] == "IMPLEMENTATION_REPAIR", repair_route

    config["enabled"] = False
    config_path.write_text(json.dumps(config), encoding="utf-8")
    rc, paused_feedback_run = run(
        root,
        "start",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0, paused_feedback_run
    rc, paused_feedback = run(
        root,
        "route-feedback",
        "--run-file", paused_feedback_run["run_file"],
        "--feedback-file", str(feedback_file),
    )
    assert rc == 0 and paused_feedback["decision"]["decision"] == "PAUSE", paused_feedback
    pause_action = paused_feedback["operator_action"]
    assert pause_action["action"] == "REVIEW_AND_RESUME_OWNER_ROUTE", paused_feedback
    assert pause_action["command"] == "order.bootstrap", paused_feedback
    assert pause_action["arguments"] == 'allow "focused" integration tests', paused_feedback
    assert pause_action["owner_command"] == (
        '/order.bootstrap "allow \\"focused\\" integration tests"'
    ), paused_feedback
    assert pause_action["recommended_commands"] == [
        pause_action["recommended_command"], "/order.code --resume"
    ], paused_feedback
    assert pause_action["resume_command"] == "/order.code --resume", paused_feedback
    rc, paused_status = run(
        root, "status", "--run-file", paused_feedback_run["run_file"]
    )
    assert rc == 0 and paused_status["operator_action"]["recommended_commands"] == [
        pause_action["recommended_command"], "/order.code --resume"
    ], paused_status
    rc, reacquired_feedback = run(
        root,
        "acquire",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0 and reacquired_feedback["action"] == "OPERATOR_BOUNDARY", reacquired_feedback
    assert reacquired_feedback["operator_action"]["recommended_commands"] == [
        pause_action["recommended_command"], "/order.code --resume"
    ], reacquired_feedback
    rc, resumed_feedback = run(
        root, "resume", "--run-file", paused_feedback_run["run_file"],
        "--reason", "operator reviewed the owner route",
    )
    assert rc == 0 and resumed_feedback["run"]["current_command"] == "order.bootstrap", resumed_feedback
    assert resumed_feedback["run"]["route_count"] == 1, resumed_feedback
    assert resumed_feedback["next_action"]["command"] == "order.bootstrap", resumed_feedback

    config["enabled"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")

    policy_feature = root / ".orderspec" / "features" / "FEAT-003-policy-reclassify"
    policy_feature.mkdir(parents=True)
    config_without_author_route = json.loads(json.dumps(config))
    config_without_author_route["rules"] = [
        rule for rule in config_without_author_route["rules"]
        if rule["id"] != "auto-author-upstream-routing"
    ]
    config_path.write_text(json.dumps(config_without_author_route), encoding="utf-8")
    rc, policy_run = run(
        root,
        "start",
        "--feature-dir", str(policy_feature),
        "--command", "order.tasks",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0, policy_run
    author_route = {
        "version": 1,
        "id": "FB-POLICY-001",
        "kind": "ROUTE",
        "reason": "UPSTREAM_DEFECT",
        "source": "order.tasks",
        "target": "order.plan",
        "severity": None,
        "destructive": False,
        "summary": "test topology is incomplete",
        "evidence": "T120 has no plan-owned failure injection mechanism",
        "interaction": None,
    }
    rc, policy_paused = run(
        root, "evaluate", "--run-file", policy_run["run_file"], "--event-file", "-",
        stdin=json.dumps(author_route),
    )
    assert rc == 0 and policy_paused["run"]["status"] == "PAUSED", policy_paused
    assert policy_paused["decision"]["basis"] == "default:route", policy_paused
    config_path.write_text(json.dumps(config), encoding="utf-8")
    rc, policy_reclassified = run(
        root,
        "acquire",
        "--feature-dir", str(policy_feature),
        "--command", "order.tasks",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0 and policy_reclassified["action"] == "RESUME_RUN", policy_reclassified
    assert policy_reclassified["run"]["current_command"] == "order.plan", policy_reclassified
    assert policy_reclassified["run"]["route_count"] == 1, policy_reclassified
    assert policy_reclassified["reconciliation"] == {
        "reason": "PAUSED_TRANSITION_RECLASSIFIED",
        "event_id": "FB-POLICY-001",
        "previous_basis": "default:route",
        "effective_basis": "auto-author-upstream-routing",
        "restored_command": "order.plan",
    }, policy_reclassified

    rc, corrupt_run = run(
        root,
        "start",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0, corrupt_run
    corrupt_path = Path(corrupt_run["run_file"])
    corrupt_state = json.loads(corrupt_path.read_text(encoding="utf-8"))
    corrupt_state["current_command"] = "order.code-check"
    corrupt_state["transition_count"] = 1
    corrupt_state["history"].append({
        "at": corrupt_state["updated_at"],
        "type": "EVENT",
        "event": {
            "version": 1, "id": "AUTO-ADVANCE-0001", "kind": "ADVANCE",
            "reason": "STAGE_COMPLETE", "source": "order.code", "target": "order.code-check",
            "severity": "LOW", "destructive": False, "summary": "", "evidence": "",
            "interaction": None,
        },
        "decision": {"decision": "AUTO_ROUTE"},
    })
    corrupt_path.write_text(json.dumps(corrupt_state), encoding="utf-8")
    rc, reconciled = run(
        root,
        "acquire",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0 and reconciled["action"] == "RESUME_RUN", reconciled
    assert Path(reconciled["run_file"]) == corrupt_path, reconciled
    assert reconciled["run"]["current_command"] == "order.code", reconciled
    assert reconciled["next_action"]["arguments"] == "--resume", reconciled
    assert reconciled["reconciliation"] == {
        "reason": "PREMATURE_ORDER_CODE_ADVANCE",
        "rejected_event_id": "AUTO-ADVANCE-0001",
        "restored_command": "order.code",
        "unchecked": 1,
        "first_unchecked": "T001",
    }, reconciled

    rc, collision_run = run(
        root,
        "start",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0, collision_run
    collision_path = Path(collision_run["run_file"])
    collision_state = json.loads(collision_path.read_text(encoding="utf-8"))
    for index in range(4):
        event = {
            "version": 1,
            "id": f"FB-{index + 1:03d}",
            "kind": "ROUTE",
            "reason": "UPSTREAM_DEFECT",
            "source": "order.code",
            "target": "order.tasks",
            "severity": None,
            "destructive": False,
            "summary": f"distinct task defect {index + 1}",
            "evidence": f"task T{index + 1:03d} has distinct missing context",
            "interaction": None,
        }
        collision_state["history"].append({
            "at": collision_state["updated_at"],
            "type": "EVENT",
            "event": event,
            "decision": {
                "decision": "PAUSE" if index == 3 else "AUTO_ROUTE",
                "basis": "auto-code-upstream-routing",
                "safety_override": "same-event cycle limit reached" if index == 3 else None,
                "event_fingerprint": "legacy-colliding-fingerprint",
            },
        })
    collision_state["status"] = "PAUSED"
    collision_state["transition_count"] = 6
    collision_state["route_count"] = 3
    collision_state["decision_counts"] = {"auto-code-upstream-routing": 4}
    collision_state["event_counts"] = {"legacy-colliding-fingerprint": 4}
    collision_path.write_text(json.dumps(collision_state), encoding="utf-8")

    rc, collision_repaired = run(
        root,
        "acquire",
        "--feature-dir", str(feature),
        "--command", "order.code",
        "--terminal-command", "order.code-check",
    )
    assert rc == 0 and collision_repaired["action"] == "RESUME_RUN", collision_repaired
    assert collision_repaired["run"]["status"] == "RUNNING", collision_repaired
    assert collision_repaired["run"]["current_command"] == "order.tasks", collision_repaired
    assert collision_repaired["run"]["route_count"] == 4, collision_repaired
    assert collision_repaired["next_action"]["command"] == "order.tasks", collision_repaired
    assert collision_repaired["reconciliation"]["reason"] == (
        "LEGACY_EVENT_FINGERPRINT_COLLISION"
    ), collision_repaired
    assert len(collision_repaired["run"]["event_counts"]) == 4, collision_repaired
    assert set(collision_repaired["run"]["event_counts"].values()) == {1}, collision_repaired

print("All workflow-supervisor tests passed")
