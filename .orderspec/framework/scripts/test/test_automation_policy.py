#!/usr/bin/env python3
"""Regression tests for automation policy classification and safety overrides."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "automation_policy.py"
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "templates" / "automation-config.json"


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
        "evidence": "plan-report.md finding P1-001",
    }
    value.update(overrides)
    return value


with tempfile.TemporaryDirectory(prefix="orderspec-automation-policy-") as temp:
    root = Path(temp)
    config = root / "automation.json"
    data = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data["enabled"] = False
    config.write_text(json.dumps(data), encoding="utf-8")

    rc, result = run(config)
    assert rc == 0 and result["rule_count"] == 6, result

    rc, result = run(config, route_event())
    assert rc == 0 and result["decision"] == "PAUSE", result
    assert result["basis"] == "automation-disabled", result

    disabled_complete = {
        "version": 1,
        "id": "EVT-000",
        "kind": "COMPLETE",
        "reason": "WORKFLOW_COMPLETE",
        "source": "order.code-check",
        "evidence": "code-report.md verdict PASS",
    }
    rc, result = run(config, disabled_complete)
    assert rc == 0 and result["decision"] == "PAUSE", result
    assert result["basis"] == "automation-disabled", result

    data["enabled"] = True
    config.write_text(json.dumps(data), encoding="utf-8")
    rc, result = run(config, route_event())
    assert rc == 0 and result["decision"] == "AUTO_ROUTE", result
    assert result["basis"] == "auto-gate-artifact-fixes", result
    fingerprint = result["event_fingerprint"]
    occurrence_key = result["occurrence_key"]

    rc, distinct = run(config, route_event(
        summary="a different mapping defect",
        evidence="plan-report.md finding P1-002",
    ), {f"event:{fingerprint}": 3, occurrence_key: 4})
    assert rc == 0 and distinct["decision"] == "AUTO_ROUTE", distinct
    assert distinct["event_fingerprint"] != fingerprint, distinct

    rc, result = run(config, route_event(
        source="order.code",
        target="order.bootstrap",
        reason="UPSTREAM_DEFECT",
    ))
    assert rc == 0 and result["decision"] == "AUTO_ROUTE", result
    assert result["basis"] == "auto-code-project-routing", result

    rc, result = run(config, route_event(
        source="order.code", target="order.tasks", reason="IMPLEMENTATION_REPAIR",
    ))
    assert rc == 0 and result["decision"] == "AUTO_ROUTE", result

    rc, result = run(config, route_event(
        source="order.tasks",
        target="order.plan",
        reason="UPSTREAM_DEFECT",
        summary="test topology is incomplete",
        evidence="T120 has no plan-owned failure injection mechanism",
    ))
    assert rc == 0 and result["decision"] == "AUTO_ROUTE", result
    assert result["basis"] == "auto-author-upstream-routing", result

    rc, result = run(config, route_event(), {f"event:{fingerprint}": 3})
    assert result["decision"] == "PAUSE", result
    assert "cycle" in result["safety_override"], result

    rc, result = run(config, route_event(), {occurrence_key: 4})
    assert result["decision"] == "PAUSE", result
    assert "rule occurrence" in result["safety_override"], result

    advance = {
        "version": 1,
        "id": "EVT-ADVANCE",
        "kind": "ADVANCE",
        "reason": "STAGE_COMPLETE",
        "source": "order.tasks",
        "target": "order.tasks-check",
    }
    rc, first_advance = run(config, advance)
    assert rc == 0 and first_advance["decision"] == "AUTO_ROUTE", first_advance
    rc, repeated_advance = run(
        config,
        advance,
        {f"event:{first_advance['event_fingerprint']}": 99},
    )
    assert rc == 0 and repeated_advance["decision"] == "AUTO_ROUTE", repeated_advance

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
            "choices": [
                {"value": "approve", "label": "Start database", "consequence": "Start the configured local database."},
                {"value": "deny", "label": "Do not start database", "consequence": "Leave the environment unchanged."},
            ],
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
        "source": "order.code-check",
        "evidence": "code-report.md verdict PASS",
    }
    rc, result = run(config, complete)
    assert rc == 0 and result["decision"] == "COMPLETE", result

    data["rules"].insert(0, {
        "id": "unsafe-runtime-route",
        "match": {"kind": "RUNTIME", "reason": "TRANSIENT_FAILURE"},
        "action": "auto_route",
    })
    config.write_text(json.dumps(data), encoding="utf-8")
    transient = {**runtime, "reason": "TRANSIENT_FAILURE"}
    rc, result = run(config, transient)
    assert rc == 0 and result["decision"] == "PAUSE", result
    assert "AUTO_ROUTE" in result["safety_override"], result

    invalid_event = route_event(target="order.nonexistent")
    rc, result = run(config, invalid_event)
    assert rc == 2 and result["ok"] is False, result

    invalid = dict(data)
    invalid["defaults"] = {**data["defaults"], "operator_input": "auto_route"}
    config.write_text(json.dumps(invalid), encoding="utf-8")
    rc, result = run(config)
    assert rc == 2 and result["ok"] is False, result

print("All automation-policy tests passed")
