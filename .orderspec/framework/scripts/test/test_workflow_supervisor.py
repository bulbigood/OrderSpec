#!/usr/bin/env python3
"""Regression tests for persistent workflow supervisor transitions."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "workflow_supervisor.py"
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "automation.json"


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

    question = {
        "version": 1,
        "id": "EVT-002",
        "kind": "OPERATOR_INPUT",
        "reason": "SEMANTIC_DECISION",
        "source": "order.plan",
        "summary": "two delivery strategies remain plausible",
        "interaction": {
            "id": "INT-001",
            "kind": "SEMANTIC_DECISION",
            "question": "Keep the current interface or add a new one?",
            "options": ["keep", "add"],
            "resume_strategy": "same_session"
        }
    }
    rc, result = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(question),
    )
    assert rc == 0 and result["run"]["status"] == "WAITING_OPERATOR", result
    assert result["run"]["pending_interaction"]["id"] == "INT-001", result

    rc, rejected = run(
        root, "answer", "--run-file", str(run_file),
        "--interaction-id", "INT-001", "--answer", "unknown",
    )
    assert rc == 2 and rejected["ok"] is False, rejected

    rc, result = run(
        root, "answer", "--run-file", str(run_file),
        "--interaction-id", "INT-001", "--answer", "keep",
    )
    assert rc == 0 and result["run"]["status"] == "RUNNING", result
    assert result["run"]["session_mode"] == "resume", result
    assert result["run"]["resume_input"]["answer"] == "keep", result

    text_question = {
        "version": 1,
        "id": "EVT-003",
        "kind": "OPERATOR_INPUT",
        "reason": "SCOPE_CLARIFICATION",
        "source": "order.plan",
        "interaction": {
            "id": "INT-002",
            "kind": "SCOPE_CLARIFICATION",
            "question": "Which bounded module owns this behavior?",
            "response_type": "text",
            "resume_strategy": "same_session"
        }
    }
    rc, result = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(text_question),
    )
    assert rc == 0 and result["run"]["status"] == "WAITING_OPERATOR", result
    rc, result = run(
        root, "answer", "--run-file", str(run_file),
        "--interaction-id", "INT-002", "--answer", "src/billing",
    )
    assert rc == 0 and result["run"]["resume_input"]["answer"] == "src/billing", result

    advance = {
        "version": 1,
        "id": "EVT-004",
        "kind": "ADVANCE",
        "reason": "STAGE_COMPLETE",
        "source": "order.plan",
        "target": "order.plan-check",
    }
    rc, result = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(advance),
    )
    assert rc == 0 and result["run"]["current_command"] == "order.plan-check", result

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
    assert resumed["run"]["history"][-1]["type"] == "OPERATOR_RESUME", resumed

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

print("All workflow-supervisor tests passed")
