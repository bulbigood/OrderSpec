#!/usr/bin/env python3
"""Regression tests for automation policy classification and safety overrides."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "automation_policy.py"
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "automation.json"


def run(config: Path, event: dict | None = None, counters: dict | None = None):
    args = [sys.executable, str(SCRIPT), "classify" if event else "validate", "--config", str(config)]
    stdin = None
    if event is not None:
        args.extend(["--event-file", "-", "--counters", json.dumps(counters or {})])
        stdin = json.dumps(event)
    result = subprocess.run(args, input=stdin, capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


def route_event(**overrides):
    value = {
        "version": 1,
        "id": "EVT-001",
        "kind": "ROUTE",
        "reason": "ARTIFACT_DEFECT",
        "source": "order.code-check",
        "target": "order.plan",
        "severity": "HIGH",
        "destructive": False,
        "summary": "mapping is incomplete",
    }
    value.update(overrides)
    return value


with tempfile.TemporaryDirectory(prefix="orderspec-automation-policy-") as temp:
    root = Path(temp)
    config = root / "automation.json"
    data = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    config.write_text(json.dumps(data), encoding="utf-8")

    rc, result = run(config)
    assert rc == 0 and result["rule_count"] == 4, result

    rc, result = run(config, route_event())
    assert rc == 0 and result["decision"] == "PAUSE", result
    assert result["basis"] == "automation-disabled", result

    data["enabled"] = True
    config.write_text(json.dumps(data), encoding="utf-8")
    rc, result = run(config, route_event())
    assert rc == 0 and result["decision"] == "AUTO_ROUTE", result
    assert result["basis"] == "auto-gate-artifact-fixes", result
    fingerprint = result["event_fingerprint"]

    rc, result = run(config, route_event(), {f"event:{fingerprint}": 3})
    assert result["decision"] == "PAUSE", result
    assert "cycle" in result["safety_override"], result

    rc, result = run(config, route_event(destructive=True))
    assert result["decision"] == "PAUSE", result
    assert "destructive" in result["safety_override"], result

    operator = {
        "version": 1,
        "id": "EVT-002",
        "kind": "OPERATOR_INPUT",
        "reason": "MUTATION_APPROVAL",
        "source": "order.code",
        "interaction": {
            "id": "INT-001",
            "kind": "MUTATION_APPROVAL",
            "question": "Start the local database?",
            "options": ["approve", "deny"],
            "exact_action": "docker compose up -d database"
        }
    }
    data["rules"].insert(0, {
        "id": "unsafe-auto-input",
        "match": {"kind": "OPERATOR_INPUT"},
        "action": "auto_route"
    })
    config.write_text(json.dumps(data), encoding="utf-8")
    rc, result = run(config, operator)
    assert rc == 0 and result["decision"] == "PAUSE", result
    assert "cannot be answered automatically" in result["safety_override"], result

    runtime = {
        "version": 1,
        "id": "EVT-003",
        "kind": "RUNTIME",
        "reason": "FRAMEWORK_ERROR",
        "source": "order.plan"
    }
    rc, result = run(config, runtime)
    assert rc == 0 and result["decision"] == "STOP", result

    complete = {
        "version": 1,
        "id": "EVT-004",
        "kind": "COMPLETE",
        "reason": "WORKFLOW_COMPLETE",
        "source": "order.code-check"
    }
    rc, result = run(config, complete)
    assert rc == 0 and result["decision"] == "COMPLETE", result

    invalid = dict(data)
    invalid["defaults"] = {**data["defaults"], "operator_input": "auto_route"}
    config.write_text(json.dumps(invalid), encoding="utf-8")
    rc, result = run(config)
    assert rc == 2 and result["ok"] is False, result

print("All automation-policy tests passed")
