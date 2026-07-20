#!/usr/bin/env python3
"""Regression tests for active work-order plan impact classification."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "plan_reconcile.py"
SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "plan-reconcile-candidate.schema.json"


def run(feature: Path, candidate: dict, operator_answer: str | None = None):
    args = [
        sys.executable,
        str(SCRIPT),
        "classify-impact",
        "--feature-dir",
        str(feature),
        "--candidate-file",
        "-",
    ]
    if operator_answer is not None:
        args.extend(["--operator-answer", operator_answer])
    result = subprocess.run(
        args,
        input=json.dumps(candidate),
        capture_output=True,
        text=True,
    )
    return result.returncode, json.loads(result.stdout)


def candidate(**overrides):
    value = {
        "version": 2,
        "change_kind": "mechanism",
        "affected_task_ids": ["T120"],
        "changed_paths": ["tests/integration/task.test.js"],
        "changed_spec_ids": ["AC-009"],
        "evidence_dependency_spec_ids": [],
        "completed_behavior": "preserved",
        "reset_required": False,
        "evidence": "The new failure seam extends only unchecked AC-009 evidence.",
    }
    value.update(overrides)
    return value


with tempfile.TemporaryDirectory(prefix="orderspec-plan-reconcile-") as temp:
    template_result = subprocess.run(
        [sys.executable, str(SCRIPT), "candidate-template"],
        capture_output=True,
        text=True,
    )
    template = json.loads(template_result.stdout)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert template_result.returncode == 0 and list(template["candidate"]) == [
        "version",
        "change_kind",
        "affected_task_ids",
        "changed_paths",
        "changed_spec_ids",
        "evidence_dependency_spec_ids",
        "completed_behavior",
        "reset_required",
        "evidence",
    ], template
    assert schema["required"] == list(template["candidate"]), schema
    assert sorted(schema["properties"]["change_kind"]["enum"]) == template["allowed_values"]["change_kind"], schema
    assert sorted(schema["properties"]["completed_behavior"]["enum"]) == template["allowed_values"]["completed_behavior"], schema

    feature = Path(temp) / ".orderspec" / "features" / "001-demo"
    feature.mkdir(parents=True)
    (feature / "tasks.md").write_text(
        """# Tasks

## Phase 1

- [X] T010 | src/services/task.service.js | REQ-001 | completed service
- [X] T020 | tests/integration/task.test.js | AC-001 | completed test

## Phase 2

- [ ] T120 | tests/integration/task.test.js | AC-009 | pending atomic failure test
- [ ] T130 | src/services/task.service.js | REQ-008 | pending history service
""",
        encoding="utf-8",
    )

    rc, data = run(feature, candidate())
    assert rc == 0 and data["classification"] == "PENDING_ONLY", data
    assert data["plan_write_permitted"] is True, data
    assert data["impact"]["affected_tasks"] == ["T120"], data
    assert data["impact"]["shared_completed_paths"] == ["T020"], data
    assert data["impact"]["evidence_dependency_tasks"] == [], data
    assert data["next_action"]["preserve_completed"] is True, data

    rc, data = run(
        feature,
        candidate(evidence_dependency_spec_ids=["REQ-001", "AC-001"]),
    )
    assert rc == 0 and data["classification"] == "PENDING_ONLY", data
    assert data["impact"]["affected_completed"] == [], data
    assert data["impact"]["evidence_dependency_tasks"] == ["T010", "T020"], data

    rc, data = run(
        feature,
        candidate(evidence_dependency_spec_ids=["REQ-001", "AC-001"]),
        "preserve_partial",
    )
    assert rc == 0 and data["classification"] == "PENDING_ONLY", data
    assert data["plan_write_permitted"] is True, data
    assert data["operator_answer"]["applied_to"] == "PENDING_ONLY", data

    rc, data = run(
        feature,
        candidate(
            affected_task_ids=["T010"],
            changed_paths=["src/services/task.service.js"],
            changed_spec_ids=["REQ-001"],
            completed_behavior="changed",
        ),
    )
    assert rc == 0 and data["classification"] == "COMPLETED_OVERLAP", data
    assert data["plan_write_permitted"] is False, data
    assert data["operator_request"]["reason"] == "SEMANTIC_DECISION", data
    assert data["operator_request"]["options"] == [
        "preserve_partial", "preview_bounded_reset"
    ], data
    assert [choice["value"] for choice in data["operator_request"]["choices"]] == data["operator_request"]["options"], data
    assert all(choice["label"] and choice["consequence"] for choice in data["operator_request"]["choices"]), data
    assert data["operator_request"]["ask_arguments"][:4] == [
        "--source", "order.plan", "--reason", "SEMANTIC_DECISION"
    ], data
    assert data["operator_request"]["ask_arguments"].count("--choice") == 2, data

    overlap_candidate = candidate(
        affected_task_ids=["T010"],
        changed_paths=["src/services/task.service.js"],
        changed_spec_ids=["REQ-001"],
        completed_behavior="changed",
    )
    rc, data = run(feature, overlap_candidate, "preserve_partial")
    assert rc == 0 and data["classification"] == "OPERATOR_PRESERVE_APPROVED", data
    assert data["plan_write_permitted"] is True, data
    assert data["operator_answer"]["applied_to"] == "COMPLETED_OVERLAP", data

    rc, data = run(feature, overlap_candidate, "preview_bounded_reset")
    assert rc == 0 and data["classification"] == "RESET_PREVIEW_REQUIRED", data
    assert data["next_action"]["apply_without_approval"] is False, data
    assert data["next_action"]["command"][-2:] == [
        "--feature-dir", str(feature.resolve())
    ], data

    rc, data = run(feature, candidate(completed_behavior="unknown"))
    assert rc == 0 and data["classification"] == "COMPLETED_OVERLAP", data

    rc, data = run(
        feature,
        candidate(
            change_kind="topology",
            affected_task_ids=["T120"],
            completed_behavior="preserved",
        ),
    )
    assert rc == 0 and data["classification"] == "COMPLETED_OVERLAP", data

    rc, data = run(
        feature,
        candidate(
            reset_required=True,
            completed_behavior="changed",
        ),
    )
    assert rc == 0 and data["classification"] == "RESET_REQUIRED", data
    assert data["operator_request"]["reason"] == "WORK_ORDER_RESET_REQUIRED", data
    assert "stop_without_changes" in data["operator_request"]["options"], data

    rc, data = run(
        feature,
        candidate(reset_required=True, completed_behavior="changed"),
        "stop_without_changes",
    )
    assert rc == 0 and data["classification"] == "STOP_WITHOUT_CHANGES", data
    assert data["plan_write_permitted"] is False, data

    rc, data = run(
        feature,
        candidate(
            change_kind="none",
            affected_task_ids=[],
            changed_paths=[],
            changed_spec_ids=[],
            evidence_dependency_spec_ids=[],
            completed_behavior="preserved",
            evidence="The existing WHERE/HOW mapping already covers the feedback.",
        ),
    )
    assert rc == 0 and data["classification"] == "NO_DELTA", data
    assert data["action"] == "ROUTE_TO_TASKS_WITHOUT_PLAN_WRITE", data

    rc, data = run(feature, candidate(affected_task_ids=["T999"]))
    assert rc == 2 and data["error_code"] == "INVALID_PLAN_RECONCILE_CANDIDATE", data
    assert data["state_mutated"] is False, data

    rc, data = run(
        feature,
        candidate(evidence_dependency_spec_ids=["AC-009"]),
    )
    assert rc == 2 and data["error_code"] == "INVALID_PLAN_RECONCILE_CANDIDATE", data
    assert "not both" in data["error"], data

print("All plan-reconcile tests passed")
