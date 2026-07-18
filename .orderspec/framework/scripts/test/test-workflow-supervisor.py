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
        "summary": "physical mapping is incomplete"
    }
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

    complete = {
        "version": 1,
        "id": "EVT-004",
        "kind": "COMPLETE",
        "reason": "WORKFLOW_COMPLETE",
        "source": "order.plan"
    }
    rc, result = run(
        root, "evaluate", "--run-file", str(run_file), "--event-file", "-",
        stdin=json.dumps(complete),
    )
    assert rc == 0 and result["decision"]["decision"] == "COMPLETE", result
    assert result["run"]["status"] == "COMPLETE", result

    rc, result = run(root, "status", "--run-file", str(run_file))
    assert rc == 0 and len(result["run"]["history"]) == 7, result

print("All workflow-supervisor tests passed")
