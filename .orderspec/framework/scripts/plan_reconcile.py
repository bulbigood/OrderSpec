#!/usr/bin/env python3
"""Classify a plan candidate delta against an active tasks baseline."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from task_progress import parse_tasks, safe_relative_path


TASK_ID_RE = re.compile(r"^T\d{3}$")
SPEC_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d{3}$")
CHANGE_KINDS = {"none", "mapping", "mechanism", "topology", "delivery_strategy"}
COMPLETED_BEHAVIOR = {"preserved", "changed", "unknown"}
CANDIDATE_KEYS = {
    "version",
    "change_kind",
    "affected_task_ids",
    "changed_paths",
    "changed_spec_ids",
    "evidence_dependency_spec_ids",
    "completed_behavior",
    "reset_required",
    "evidence",
}


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def read_candidate(value: str) -> Any:
    try:
        if value == "-":
            return json.loads(sys.stdin.read())
        return json.loads(Path(value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid candidate JSON: {exc}") from exc


def string_list(value: Any, label: str, pattern: re.Pattern[str] | None = None) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    if pattern is not None:
        invalid = [item for item in value if not pattern.fullmatch(item)]
        if invalid:
            raise ValueError(f"{label} contains invalid values: {', '.join(invalid)}")
    return value


def validate_candidate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("candidate must be a JSON object")
    unknown = sorted(set(value) - CANDIDATE_KEYS)
    missing = sorted(CANDIDATE_KEYS - set(value))
    if unknown:
        raise ValueError(f"candidate has unknown fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"candidate is missing fields: {', '.join(missing)}")
    if value.get("version") != 2:
        raise ValueError("candidate.version must be 2; regenerate it with candidate-template")
    change_kind = value.get("change_kind")
    if change_kind not in CHANGE_KINDS:
        raise ValueError(f"candidate.change_kind must be one of: {', '.join(sorted(CHANGE_KINDS))}")
    affected_task_ids = string_list(value.get("affected_task_ids"), "candidate.affected_task_ids", TASK_ID_RE)
    changed_paths = string_list(value.get("changed_paths"), "candidate.changed_paths")
    unsafe = [path for path in changed_paths if not safe_relative_path(path)]
    if unsafe:
        raise ValueError(f"candidate.changed_paths contains unsafe paths: {', '.join(unsafe)}")
    changed_spec_ids = string_list(
        value.get("changed_spec_ids"), "candidate.changed_spec_ids", SPEC_ID_RE
    )
    evidence_dependency_spec_ids = string_list(
        value.get("evidence_dependency_spec_ids"),
        "candidate.evidence_dependency_spec_ids",
        SPEC_ID_RE,
    )
    ambiguous_spec_ids = sorted(set(changed_spec_ids).intersection(evidence_dependency_spec_ids))
    if ambiguous_spec_ids:
        raise ValueError(
            "candidate Spec IDs must be classified as changed or evidence-only, not both: "
            + ", ".join(ambiguous_spec_ids)
        )
    completed_behavior = value.get("completed_behavior")
    if completed_behavior not in COMPLETED_BEHAVIOR:
        raise ValueError(
            "candidate.completed_behavior must be one of: "
            + ", ".join(sorted(COMPLETED_BEHAVIOR))
        )
    if not isinstance(value.get("reset_required"), bool):
        raise ValueError("candidate.reset_required must be a boolean")
    evidence = value.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("candidate.evidence must be a non-empty string")
    if change_kind == "none" and (
        affected_task_ids
        or changed_paths
        or changed_spec_ids
        or evidence_dependency_spec_ids
        or value["reset_required"]
    ):
        raise ValueError("change_kind none requires empty affected lists and reset_required=false")
    return {
        "version": 2,
        "change_kind": change_kind,
        "affected_task_ids": affected_task_ids,
        "changed_paths": changed_paths,
        "changed_spec_ids": changed_spec_ids,
        "evidence_dependency_spec_ids": evidence_dependency_spec_ids,
        "completed_behavior": completed_behavior,
        "reset_required": value["reset_required"],
        "evidence": evidence.strip(),
    }


def task_refs(record: dict[str, Any]) -> set[str]:
    parts = record["line"].split(" | ")
    if len(parts) < 3:
        return set()
    return {item.strip() for item in parts[2].split(",") if item.strip()}


def operator_request(classification: str) -> dict[str, Any]:
    if classification == "RESET_REQUIRED":
        choices = [
            {
                "value": "preview_bounded_reset",
                "label": "Preview the bounded reset",
                "consequence": (
                    "Run only a read-only rollback preview. No implementation or task marker "
                    "is changed; applying the reset later requires separate mutation approval."
                ),
            },
            {
                "value": "stop_without_changes",
                "label": "Stop without changes",
                "consequence": "Leave the plan, work order, implementation, and task markers unchanged.",
            },
        ]
        return {
            "reason": "WORK_ORDER_RESET_REQUIRED",
            "interaction_id": "plan-active-work-order-reset",
            "question": "The candidate cannot preserve the active work-order baseline. Choose the bounded next step.",
            "options": [choice["value"] for choice in choices],
            "choices": choices,
            "resume_strategy": "same_session",
        }
    choices = [
        {
            "value": "preserve_partial",
            "label": "Preserve completed work",
            "consequence": (
                "Apply the minimum plan correction and reconcile only unchecked tasks; completed "
                "task markers and implementation remain unchanged. Choose this only when completed "
                "behavior remains valid."
            ),
        },
        {
            "value": "preview_bounded_reset",
            "label": "Preview the bounded reset",
            "consequence": (
                "Run only a read-only rollback preview. No implementation or task marker is changed; "
                "applying the reset later requires separate mutation approval."
            ),
        },
    ]
    return {
        "reason": "SEMANTIC_DECISION",
        "interaction_id": "plan-active-work-order-impact",
        "question": "A plan change affects obligations owned by completed tasks. Choose how to handle the active work-order baseline.",
        "options": [choice["value"] for choice in choices],
        "choices": choices,
        "resume_strategy": "same_session",
    }


def classify(
    feature_dir: Path,
    candidate: dict[str, Any],
    operator_answer: str | None = None,
) -> dict[str, Any]:
    tasks_path = feature_dir / "tasks.md"
    records, errors = parse_tasks(tasks_path)
    if errors:
        raise ValueError("invalid tasks baseline: " + "; ".join(errors))
    by_id = {record["task_id"]: record for record in records}
    unknown_tasks = sorted(set(candidate["affected_task_ids"]) - set(by_id))
    if unknown_tasks:
        raise ValueError(f"candidate references unknown task IDs: {', '.join(unknown_tasks)}")

    completed = [record["task_id"] for record in records if record["status"].lower() == "x"]
    unchecked = [record["task_id"] for record in records if record["status"] == " "]
    changed_spec_ids = set(candidate["changed_spec_ids"])
    changed_spec_inferred = {
        record["task_id"]
        for record in records
        if task_refs(record).intersection(changed_spec_ids)
    }
    evidence_dependency_spec_ids = set(candidate["evidence_dependency_spec_ids"])
    evidence_dependency_tasks = {
        record["task_id"]
        for record in records
        if task_refs(record).intersection(evidence_dependency_spec_ids)
    }
    path_inferred = {
        record["task_id"] for record in records if record["path"] in candidate["changed_paths"]
    }
    explicit = set(candidate["affected_task_ids"])
    affected = (
        explicit | changed_spec_inferred
        if (explicit or changed_spec_inferred)
        else path_inferred
    )
    affected_completed = sorted(affected.intersection(completed))
    affected_unchecked = sorted(affected.intersection(unchecked))
    shared_completed_paths = sorted(path_inferred.intersection(completed))

    if candidate["change_kind"] == "none":
        classification = "NO_DELTA"
        action = "ROUTE_TO_TASKS_WITHOUT_PLAN_WRITE"
        plan_write_permitted = False
    elif candidate["reset_required"]:
        classification = "RESET_REQUIRED"
        action = "ASK_OPERATOR"
        plan_write_permitted = False
    elif candidate["change_kind"] in {"topology", "delivery_strategy"} and completed:
        classification = "COMPLETED_OVERLAP"
        action = "ASK_OPERATOR"
        plan_write_permitted = False
    elif candidate["completed_behavior"] != "preserved" or affected_completed:
        classification = "COMPLETED_OVERLAP"
        action = "ASK_OPERATOR"
        plan_write_permitted = False
    else:
        classification = "PENDING_ONLY"
        action = "PRESERVE_AND_RECONCILE_PENDING"
        plan_write_permitted = True

    base_classification = classification
    if operator_answer is not None:
        if classification == "PENDING_ONLY" and operator_answer == "preserve_partial":
            # A persisted answer may outlive a framework/candidate correction that
            # narrows an earlier conservative COMPLETED_OVERLAP to PENDING_ONLY.
            # Preserve is already the deterministic action, so accepting it is
            # idempotent and cannot authorize broader or destructive work.
            pass
        else:
            allowed_answers = {
                "COMPLETED_OVERLAP": {"preserve_partial", "preview_bounded_reset"},
                "RESET_REQUIRED": {"preview_bounded_reset", "stop_without_changes"},
            }.get(classification)
            if allowed_answers is None:
                raise ValueError(
                    f"operator answer is stale for deterministic classification {classification}"
                )
            if operator_answer not in allowed_answers:
                raise ValueError(
                    f"operator answer for {classification} must be one of: "
                    + ", ".join(sorted(allowed_answers))
                )
            if operator_answer == "preserve_partial":
                classification = "OPERATOR_PRESERVE_APPROVED"
                action = "PRESERVE_AND_RECONCILE_PENDING"
                plan_write_permitted = True
            elif operator_answer == "preview_bounded_reset":
                classification = "RESET_PREVIEW_REQUIRED"
                action = "PREVIEW_BOUNDED_RESET"
                plan_write_permitted = False
            else:
                classification = "STOP_WITHOUT_CHANGES"
                action = "STOP_WITHOUT_CHANGES"
                plan_write_permitted = False

    payload: dict[str, Any] = {
        "ok": True,
        "action": action,
        "classification": classification,
        "plan_write_permitted": plan_write_permitted,
        "feature_dir": str(feature_dir),
        "tasks_file": str(tasks_path),
        "inventory": {
            "completed": completed,
            "unchecked": unchecked,
        },
        "impact": {
            "affected_tasks": sorted(affected),
            "affected_completed": affected_completed,
            "affected_unchecked": affected_unchecked,
            "shared_completed_paths": shared_completed_paths,
            "evidence_dependency_tasks": sorted(evidence_dependency_tasks),
        },
        "candidate": candidate,
    }
    if operator_answer is not None:
        payload["operator_answer"] = {
            "value": operator_answer,
            "applied_to": base_classification,
        }
    if classification == "NO_DELTA":
        payload["next_action"] = {
            "command": "order.tasks",
            "arguments": "",
            "reason": "plan mapping is unchanged; refine only unchecked work",
        }
    elif classification in {"PENDING_ONLY", "OPERATOR_PRESERVE_APPROVED"}:
        payload["next_action"] = {
            "action": "APPLY_CANDIDATE_THEN_RECONCILE_PENDING_TASKS",
            "command": "order.tasks",
            "arguments": "",
            "preserve_completed": True,
        }
    elif classification == "RESET_PREVIEW_REQUIRED":
        payload["next_action"] = {
            "action": "RUN_RESET_PREVIEW_THEN_REQUEST_MUTATION_APPROVAL",
            "command": [
                sys.executable,
                str(Path(__file__).resolve().parent / "work_order.py"),
                "rollback",
                "--feature-dir",
                str(feature_dir),
            ],
            "apply_without_approval": False,
        }
    elif classification == "STOP_WITHOUT_CHANGES":
        payload["next_action"] = {
            "action": "LEAVE_ACTIVE_BASELINE_UNCHANGED",
        }
    else:
        request = operator_request(classification)
        request["ask_arguments"] = [
            "--source",
            "order.plan",
            "--reason",
            request["reason"],
            "--interaction-id",
            request["interaction_id"],
            "--question",
            request["question"],
            *[
                value
                for choice in request["choices"]
                for value in (
                    "--choice",
                    choice["value"],
                    choice["label"],
                    choice["consequence"],
                )
            ],
            "--summary",
            f"active work-order impact classified as {classification}",
            "--evidence",
            candidate["evidence"],
        ]
        payload["operator_request"] = request
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify an order.plan candidate delta")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("candidate-template")
    classify_parser = sub.add_parser("classify-impact")
    classify_parser.add_argument("--feature-dir", required=True)
    classify_parser.add_argument("--candidate-file", required=True, help="JSON file or - for stdin")
    classify_parser.add_argument(
        "--operator-answer",
        choices=["preserve_partial", "preview_bounded_reset", "stop_without_changes"],
    )
    args = parser.parse_args()
    try:
        if args.command == "candidate-template":
            emit({
                "ok": True,
                "candidate": {
                    "version": 2,
                    "change_kind": "none",
                    "affected_task_ids": [],
                    "changed_paths": [],
                    "changed_spec_ids": [],
                    "evidence_dependency_spec_ids": [],
                    "completed_behavior": "preserved",
                    "reset_required": False,
                    "evidence": "<exact repository and work-order evidence>",
                },
                "allowed_values": {
                    "change_kind": sorted(CHANGE_KINDS),
                    "completed_behavior": sorted(COMPLETED_BEHAVIOR),
                },
            })
            return 0
        feature_dir = Path(args.feature_dir).resolve()
        if not feature_dir.is_dir():
            raise ValueError("feature directory must exist")
        candidate = validate_candidate(read_candidate(args.candidate_file))
        emit(classify(feature_dir, candidate, args.operator_answer))
        return 0
    except ValueError as exc:
        emit({
            "ok": False,
            "error_code": "INVALID_PLAN_RECONCILE_CANDIDATE",
            "error": str(exc),
            "state_mutated": False,
        })
        return 2


if __name__ == "__main__":
    sys.exit(main())
