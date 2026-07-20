#!/usr/bin/env python3
"""Persistent runtime-neutral supervisor state for OrderSpec automation.

Runtime adapters submit typed events after an agent command finishes or asks a
question. The supervisor classifies the event, advances or pauses the run, and
persists enough state to resume after an operator answer or process failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import secrets
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

from frontmatter import extract_yaml_frontmatter

from automation_policy import (
    ADVANCE_TARGETS,
    COMMANDS,
    CONFIG_PATH,
    HARD_OPERATOR_REASONS,
    KINDS,
    REASONS_BY_KIND,
    ROUTE_TARGETS,
    TERMINAL_COMMANDS,
    classify,
    event_fingerprint,
    load_valid_config,
    validate_event,
)
from workflow_feedback import read_report, recommended_command


RUN_ID_RE = re.compile(r"^RUN-[0-9a-f]{16}$")
STATUSES = {"RUNNING", "WAITING_OPERATOR", "PAUSED", "STOPPED", "COMPLETE"}
TERMINAL_REPORTS = {
    "order.spec-check": "spec-report.md",
    "order.plan-check": "plan-report.md",
    "order.tasks-check": "tasks-report.md",
    "order.code-check": "code-report.md",
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def safe_project_root(value: str) -> Path:
    root = Path(value).resolve()
    if not (root / ".orderspec").is_dir():
        raise ValueError("project root must contain .orderspec")
    return root


def safe_feature_dir(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    feature = Path(value)
    if not feature.is_absolute():
        feature = root / feature
    feature = feature.resolve()
    expected = (root / ".orderspec" / "features").resolve()
    try:
        feature.relative_to(expected)
    except ValueError as exc:
        raise ValueError("feature directory must be under .orderspec/features") from exc
    if not feature.is_dir():
        raise ValueError("feature directory must exist")
    return feature


def run_store(root: Path, feature: Path | None) -> Path:
    if feature is not None:
        return feature / ".state" / "runs"
    return root / ".orderspec" / "state" / "runs"


def create_run(store: Path, state: dict[str, Any]) -> Path:
    store.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        run_id = f"RUN-{secrets.token_hex(8)}"
        path = store / f"{run_id}.json"
        try:
            with path.open("x", encoding="utf-8") as handle:
                state["id"] = run_id
                json.dump(state, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            return path
        except FileExistsError:
            continue
    raise ValueError("could not allocate a unique run ID")


def new_run_state(
    root: Path,
    feature: Path | None,
    command: str,
    terminal_command: str,
    session_mode: str,
) -> dict[str, Any]:
    timestamp = now()
    return {
        "version": 1,
        "id": "",
        "status": "RUNNING",
        "project_root": str(root),
        "feature_dir": str(feature) if feature else None,
        "current_command": command,
        "terminal_command": terminal_command,
        "created_at": timestamp,
        "updated_at": timestamp,
        "transition_count": 0,
        "route_count": 0,
        "decision_counts": {},
        "event_counts": {},
        "pending_interaction": None,
        "resume_input": None,
        "session_mode": session_mode,
        "history": [{"at": timestamp, "type": "RUN_STARTED", "command": command}],
    }


def initial_command(state: dict[str, Any]) -> str | None:
    history = state.get("history")
    if not isinstance(history, list) or not history or not isinstance(history[0], dict):
        return None
    first = history[0]
    if first.get("type") != "RUN_STARTED" or not isinstance(first.get("command"), str):
        return None
    return first["command"]


def load_state(path: Path, root: Path | None = None) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid run state {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("run state must be an object")
    required = {
        "version", "id", "status", "project_root", "feature_dir", "current_command",
        "created_at", "updated_at", "transition_count", "route_count", "decision_counts",
        "event_counts", "pending_interaction", "resume_input", "session_mode", "history",
    }
    required.add("terminal_command")
    if set(data) != required:
        raise ValueError(f"run state fields must be exactly: {sorted(required)}")
    if data.get("version") != 1 or not RUN_ID_RE.fullmatch(str(data.get("id", ""))):
        raise ValueError("invalid run state version or id")
    if path.stem != data["id"]:
        raise ValueError("run state ID does not match its filename")
    if data.get("status") not in STATUSES:
        raise ValueError("invalid run status")
    if data.get("current_command") not in COMMANDS:
        raise ValueError("invalid current command")
    if data.get("terminal_command") not in TERMINAL_COMMANDS:
        raise ValueError("invalid terminal command")
    if data.get("session_mode") not in {"fresh", "resume", "compact"}:
        raise ValueError("invalid session mode")
    for key in ("project_root", "created_at", "updated_at"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"run state {key} must be a non-empty string")
    feature_value = data.get("feature_dir")
    if feature_value is not None and (not isinstance(feature_value, str) or not feature_value.strip()):
        raise ValueError("run state feature_dir must be a non-empty string or null")
    for key in ("transition_count", "route_count"):
        if not isinstance(data.get(key), int) or isinstance(data[key], bool) or data[key] < 0:
            raise ValueError(f"run state {key} must be a non-negative integer")
    for key in ("decision_counts", "event_counts"):
        value = data.get(key)
        if not isinstance(value, dict) or any(
            not isinstance(name, str) or not isinstance(count, int) or isinstance(count, bool) or count < 0
            for name, count in value.items()
        ):
            raise ValueError(f"run state {key} must contain non-negative integer counters")
    if not isinstance(data.get("history"), list) or any(not isinstance(item, dict) for item in data["history"]):
        raise ValueError("run history must be an array of objects")
    for key in ("pending_interaction", "resume_input"):
        if data.get(key) is not None and not isinstance(data[key], dict):
            raise ValueError(f"run state {key} must be an object or null")
    if root is not None and data.get("project_root") != str(root):
        raise ValueError("run state belongs to a different project root")
    if root is not None and feature_value is not None:
        try:
            Path(feature_value).resolve().relative_to((root / ".orderspec" / "features").resolve())
        except ValueError as exc:
            raise ValueError("run state feature_dir is outside .orderspec/features") from exc
    return data


def resolve_run_path(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to((root / ".orderspec").resolve())
    except ValueError as exc:
        raise ValueError("run file must be under .orderspec") from exc
    return path


def resolve_feedback_path(root: Path, state: dict[str, Any], value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    stores = [(root / ".orderspec" / "state" / "feedback").resolve()]
    if state.get("feature_dir"):
        stores.append((Path(state["feature_dir"]) / ".state" / "feedback").resolve())
    if not any(path.parent == store for store in stores):
        raise ValueError("feedback file must belong to the run's feature or project feedback store")
    if path.suffix != ".json":
        raise ValueError("feedback file must be JSON")
    return path


def validate_terminal_evidence(root: Path, state: dict[str, Any], event: dict[str, Any]) -> None:
    value = event["evidence"]
    report = Path(value)
    if not report.is_absolute():
        report = root / report
    report = report.resolve()
    expected_name = TERMINAL_REPORTS[event["source"]]
    if report.name != expected_name:
        raise ValueError(f"COMPLETE evidence must reference {expected_name}")
    try:
        report.relative_to((root / ".orderspec").resolve())
    except ValueError as exc:
        raise ValueError("COMPLETE evidence must be under .orderspec") from exc
    feature_value = state.get("feature_dir")
    if feature_value is not None and report != (Path(feature_value) / expected_name).resolve():
        raise ValueError("COMPLETE evidence does not belong to the run feature")
    try:
        metadata = extract_yaml_frontmatter(report.read_text(encoding="utf-8")).get("orderspec", {})
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"cannot read COMPLETE evidence: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("COMPLETE evidence has invalid frontmatter")
    if metadata.get("artifact") != "gate_report" or metadata.get("command") != event["source"]:
        raise ValueError("COMPLETE evidence is not the terminal command's canonical gate report")
    if metadata.get("verdict") != "PASS":
        raise ValueError("COMPLETE evidence gate verdict must be PASS")


def validate_order_code_boundary(state: dict[str, Any], event: dict[str, Any]) -> None:
    """Reject ROUTE/ADVANCE events until order.code has closed local attempt state."""
    if event["source"] != "order.code" or event["kind"] not in {"ROUTE", "ADVANCE"}:
        return
    feature_value = state.get("feature_dir")
    if not feature_value:
        raise ValueError("order.code boundary requires a feature-scoped supervisor run")
    from code_workflow import blocking_attempts

    blocking, errors = blocking_attempts(Path(feature_value).resolve())
    if errors:
        raise ValueError("invalid order.code attempt inventory: " + "; ".join(errors))
    if blocking:
        details = ", ".join(
            f"{attempt['attempt_id']}:{attempt.get('finish_status') or 'active'}"
            for attempt in blocking
        )
        raise ValueError(
            "order.code command boundary rejected; finish or mark/clean attempts before supervisor event: "
            + details
        )
    if event["kind"] == "ADVANCE":
        from task_progress import parse_tasks

        records, task_errors = parse_tasks(Path(feature_value).resolve() / "tasks.md")
        if task_errors:
            raise ValueError("order.code ADVANCE rejected; invalid tasks: " + "; ".join(task_errors))
        unchecked = [record["task_id"] for record in records if record["status"] == " "]
        if unchecked:
            raise ValueError(
                "order.code ADVANCE rejected; "
                f"{len(unchecked)} unchecked tasks remain; continue at {unchecked[0]}"
            )


def reconcile_premature_code_gate(state: dict[str, Any]) -> dict[str, Any] | None:
    """Restore order.code when a persisted stale ADVANCE skipped unfinished tasks."""
    if (
        initial_command(state) != "order.code"
        or state.get("status") != "RUNNING"
        or state.get("current_command") != "order.code-check"
        or not state.get("feature_dir")
    ):
        return None
    history = state.get("history", [])
    if not history or not isinstance(history[-1], dict):
        return None
    event = history[-1].get("event")
    if not isinstance(event, dict) or not (
        event.get("kind") == "ADVANCE"
        and event.get("source") == "order.code"
        and event.get("target") == "order.code-check"
    ):
        return None
    from task_progress import parse_tasks

    records, errors = parse_tasks(Path(state["feature_dir"]).resolve() / "tasks.md")
    if errors:
        return None
    unchecked = [record["task_id"] for record in records if record["status"] == " "]
    if not unchecked:
        return None
    timestamp = now()
    reconciliation = {
        "reason": "PREMATURE_ORDER_CODE_ADVANCE",
        "rejected_event_id": event.get("id"),
        "restored_command": "order.code",
        "unchecked": len(unchecked),
        "first_unchecked": unchecked[0],
    }
    state["current_command"] = "order.code"
    state["updated_at"] = timestamp
    state["session_mode"] = "resume"
    state["history"].append({
        "at": timestamp,
        "type": "RUN_RECONCILED",
        **reconciliation,
    })
    return reconciliation


def cmd_start(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    feature = safe_feature_dir(root, args.feature_dir)
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    config = load_valid_config(config_path)
    store = run_store(root, feature)
    state = new_run_state(
        root, feature, args.command, args.terminal_command, config["context"]["between_commands"]
    )
    path = create_run(store, state)
    emit({"ok": True, "run_file": str(path), "run": state})
    return 0


def cmd_acquire(args: argparse.Namespace) -> int:
    """Atomically create a workflow run or attach its latest unfinished lease."""
    root = safe_project_root(args.project_root)
    feature = safe_feature_dir(root, args.feature_dir)
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    config = load_valid_config(config_path)
    store = run_store(root, feature)
    store.mkdir(parents=True, exist_ok=True)
    lock_path = store / ".acquire.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        matching: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(store.glob("RUN-*.json")):
            state = load_state(path, root)
            if (
                state["feature_dir"] == (str(feature) if feature else None)
                and state["terminal_command"] == args.terminal_command
                and initial_command(state) == args.command
            ):
                matching.append((path, state))
        def order_key(item: tuple[Path, dict[str, Any]]) -> tuple[str, int, str]:
            return item[1]["created_at"], item[0].stat().st_mtime_ns, item[1]["id"]
        terminal_runs = [
            item for item in matching if item[1]["status"] in {"STOPPED", "COMPLETE"}
        ]
        terminal_barrier = max(terminal_runs, key=order_key) if terminal_runs else None
        active_runs = [
            item for item in matching if item[1]["status"] not in {"STOPPED", "COMPLETE"}
        ]
        candidates = [
            item
            for item in active_runs
            if terminal_barrier is None or order_key(item) > order_key(terminal_barrier)
        ]
        if candidates:
            path, state = max(candidates, key=order_key)
            superseded = [str(item[0]) for item in active_runs if item[0] != path]
            created = False
        else:
            state = new_run_state(
                root,
                feature,
                args.command,
                args.terminal_command,
                config["context"]["between_commands"],
            )
            path = create_run(store, state)
            superseded = [str(item[0]) for item in active_runs]
            created = True
        reconciliation = None
        if not created:
            reconciliation = reconcile_paused_transition(state, config)
            if reconciliation is None:
                reconciliation = reconcile_premature_code_gate(state)
        if reconciliation is not None:
            atomic_json(path, state)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    if state["status"] == "RUNNING":
        payload = {
            "ok": True,
            "action": "STARTED_RUN" if created else "RESUME_RUN",
            "terminal": False,
            "continuation_required": True,
            "run_file": str(path),
            "run": state,
            "superseded_active_runs": superseded,
            "next_action": {
                "action": "EXECUTE_CURRENT_COMMAND",
                "command": state["current_command"],
                "arguments": "--resume" if state["current_command"] == "order.code" else "",
            },
            "final_response": {
                "permitted": False,
                "reason": "NON_TERMINAL_WORKFLOW_STATE",
            },
        }
        if reconciliation is not None:
            payload["reconciliation"] = reconciliation
        emit(payload)
        return 0

    operator_action = operator_boundary_action(root, path, state)
    emit({
        "ok": True,
        "action": "OPERATOR_BOUNDARY",
        "terminal": True,
        "continuation_required": False,
        "run_file": str(path),
        "run": state,
        "superseded_active_runs": superseded,
        "operator_action": operator_action,
    })
    return 0


def history_event_items(state: dict[str, Any], *, exclude_last: bool = False) -> list[dict[str, Any]]:
    items = [
        item
        for item in state["history"]
        if item.get("type") == "EVENT"
        and isinstance(item.get("event"), dict)
        and isinstance(item.get("decision"), dict)
    ]
    return items[:-1] if exclude_last and items else items


def semantic_event_counts(state: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in history_event_items(state):
        fingerprint = event_fingerprint(item["event"])
        counts[fingerprint] = counts.get(fingerprint, 0) + 1
    return counts


def counters_for(state: dict[str, Any], *, exclude_last: bool = False) -> dict[str, int]:
    counters = {
        "transitions": state["transition_count"],
        "routes": state["route_count"],
    }
    for item in history_event_items(state, exclude_last=exclude_last):
        fingerprint = event_fingerprint(item["event"])
        basis = item["decision"].get("basis")
        counters[f"event:{fingerprint}"] = counters.get(f"event:{fingerprint}", 0) + 1
        if isinstance(basis, str) and basis:
            key = f"rule:{basis}:event:{fingerprint}"
            counters[key] = counters.get(key, 0) + 1
    return counters


def root_recommended_command(state: dict[str, Any]) -> str:
    root_command = initial_command(state) or state["current_command"]
    return f"/{root_command}" + (" --resume" if root_command == "order.code" else "")


def latest_boundary_event(state: dict[str, Any]) -> dict[str, Any] | None:
    items = history_event_items(state)
    return items[-1]["event"] if items else None


def operator_boundary_action(
    root: Path,
    run_path: Path,
    state: dict[str, Any],
    route_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "-C",
        str(root),
        "status",
        "--run-file",
        str(run_path),
    ]
    if state["status"] == "WAITING_OPERATOR":
        interaction = state["pending_interaction"]
        answer_base = [
            sys.executable,
            str(Path(__file__).resolve()),
            "-C",
            str(root),
            "answer",
            "--run-file",
            str(run_path),
            "--interaction-id",
            interaction["id"],
            "--answer",
        ]
        action: dict[str, Any] = {
            "action": "ANSWER_OPERATOR_INTERACTION",
            "status_command": status_command,
            "interaction": interaction,
        }
        if interaction.get("response_type", "choice") == "choice":
            replies = interaction.get("options", [])
            choices = interaction.get("choices")
            structured_choices = (
                choices
                if isinstance(choices, list)
                and [choice.get("value") for choice in choices if isinstance(choice, dict)] == replies
                else [{"value": reply} for reply in replies]
            )
            action.update({
                "reply_instruction": "Reply with exactly one value from recommended_replies.",
                "recommended_replies": replies,
                "choices": structured_choices,
                "answer_commands": [
                    {"reply": reply, "command": shlex.join([*answer_base, reply])}
                    for reply in replies
                ],
                "presentation": {
                    "language": "user_configured",
                    "localize": [
                        "interaction.question",
                        "choices.label",
                        "choices.consequence",
                        "reply_instruction",
                    ],
                    "preserve_verbatim": [
                        "recommended_replies",
                        "answer_commands.command",
                    ],
                    "explain_each_choice": all(
                        isinstance(choice, dict)
                        and bool(choice.get("label"))
                        and bool(choice.get("consequence"))
                        for choice in structured_choices
                    ),
                },
            })
        else:
            action.update({
                "reply_instruction": "Reply with the requested bounded text.",
                "answer_command_template": shlex.join([*answer_base, "<answer>"]),
            })
        return action
    if state["status"] != "PAUSED":
        return {
            "action": "REVIEW_EXISTING_RUN_BOUNDARY",
            "status_command": status_command,
        }

    event = latest_boundary_event(state)
    event_id = event.get("id") if isinstance(event, dict) else "unknown"
    source = event.get("source") if isinstance(event, dict) else state["current_command"]
    target = event.get("target") if isinstance(event, dict) else None
    reason = f"reviewed paused event {event_id}: {source}"
    if isinstance(target, str):
        reason += f" -> {target}"
    resume_supervisor = shlex.join([
        sys.executable,
        str(Path(__file__).resolve()),
        "-C",
        str(root),
        "resume",
        "--run-file",
        str(run_path),
        "--reason",
        reason,
    ])
    resume_root = root_recommended_command(state)
    action: dict[str, Any] = {
        "action": "REVIEW_AND_RESUME_WORKFLOW",
        "status_command": status_command,
        "recommended_command": resume_supervisor,
        "resume_command": resume_root,
        "recommended_commands": [resume_supervisor, resume_root],
    }
    if isinstance(event, dict):
        action["pending_event"] = {
            key: event.get(key) for key in ("id", "kind", "source", "target")
        }
    if event and event.get("kind") == "ROUTE":
        action["action"] = "REVIEW_AND_RESUME_OWNER_ROUTE"
        action["command"] = event.get("target")
        if route_context is not None:
            action["arguments"] = route_context["requested_change"]
            action["owner_command"] = route_context["recommended_command"]
    return action


def reconcile_paused_transition(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    """Apply a previously paused legal transition when current policy now accepts it."""
    if state.get("status") != "PAUSED":
        return None
    items = history_event_items(state)
    if not items:
        return None
    last = items[-1]
    old_decision = last["decision"]
    event = last["event"]
    kind = event.get("kind")
    source = event.get("source")
    target = event.get("target")
    legal = (
        kind == "ROUTE" and target in ROUTE_TARGETS.get(source, set())
    ) or (
        kind == "ADVANCE" and ADVANCE_TARGETS.get(source) == target
    )
    if not legal or source != state.get("current_command"):
        return None
    effective = classify(config, event, counters_for(state, exclude_last=True))
    if effective["decision"] != "AUTO_ROUTE":
        return None

    timestamp = now()
    state["status"] = "RUNNING"
    state["current_command"] = target
    state["transition_count"] += 1
    if kind == "ROUTE":
        state["route_count"] += 1
    state["pending_interaction"] = None
    state["resume_input"] = None
    state["session_mode"] = effective["context_strategy"]
    state["updated_at"] = timestamp
    state["event_counts"] = semantic_event_counts(state)
    legacy_collision = old_decision.get("safety_override") in {
        "same-event cycle limit reached",
        "rule occurrence limit reached",
    }
    reconciliation = {
        "reason": (
            "LEGACY_EVENT_FINGERPRINT_COLLISION"
            if legacy_collision
            else "PAUSED_TRANSITION_RECLASSIFIED"
        ),
        "event_id": event.get("id"),
        "previous_basis": old_decision.get("basis"),
        "effective_basis": effective.get("basis"),
        "restored_command": target,
    }
    if legacy_collision:
        reconciliation.update({
            "old_fingerprint": old_decision.get("event_fingerprint"),
            "semantic_fingerprint": effective["event_fingerprint"],
        })
    state["history"].append({
        "at": timestamp,
        "type": "RUN_RECONCILED",
        **reconciliation,
        "effective_decision": effective,
    })
    return reconciliation


def evaluate_event(
    root: Path,
    run_path: Path,
    state: dict[str, Any],
    config_path: Path,
    event: dict[str, Any],
    route_context: dict[str, Any] | None = None,
) -> int:
    if state["status"] != "RUNNING":
        raise ValueError(f"cannot evaluate event while run status is {state['status']}")
    config = load_valid_config(config_path)
    if event["source"] != state["current_command"]:
        raise ValueError(
            f"event source {event['source']} does not match current command {state['current_command']}"
        )
    if event["kind"] == "ADVANCE" and ADVANCE_TARGETS.get(event["source"]) != event["target"]:
        raise ValueError(
            f"illegal ADVANCE transition {event['source']} -> {event['target']}"
        )
    if event["kind"] == "ROUTE" and event["target"] not in ROUTE_TARGETS[event["source"]]:
        raise ValueError(
            f"illegal ROUTE transition {event['source']} -> {event['target']}"
        )
    if event["kind"] == "COMPLETE" and event["source"] != state["terminal_command"]:
        raise ValueError(
            f"COMPLETE requires terminal command {state['terminal_command']}, got {event['source']}"
        )
    validate_order_code_boundary(state, event)
    decision = classify(config, event, counters_for(state))
    if decision["decision"] == "COMPLETE":
        validate_terminal_evidence(root, state, event)
    timestamp = now()
    fingerprint = decision["event_fingerprint"]
    state["event_counts"][fingerprint] = state["event_counts"].get(fingerprint, 0) + 1
    basis = decision["basis"]
    state["decision_counts"][basis] = state["decision_counts"].get(basis, 0) + 1
    state["updated_at"] = timestamp
    state["resume_input"] = None
    state["history"].append({"at": timestamp, "type": "EVENT", "event": event, "decision": decision})

    if decision["decision"] == "AUTO_ROUTE":
        state["transition_count"] += 1
        if event["kind"] == "ROUTE":
            state["route_count"] += 1
        state["current_command"] = event["target"]
        state["status"] = "RUNNING"
        state["pending_interaction"] = None
        state["session_mode"] = decision["context_strategy"]
    elif decision["decision"] == "RETRY":
        state["transition_count"] += 1
        state["status"] = "RUNNING"
        state["pending_interaction"] = None
        state["session_mode"] = decision["context_strategy"]
    elif decision["decision"] == "PAUSE":
        state["status"] = "WAITING_OPERATOR" if event["kind"] == "OPERATOR_INPUT" else "PAUSED"
        state["pending_interaction"] = event["interaction"] if event["kind"] == "OPERATOR_INPUT" else None
        state["session_mode"] = decision["context_strategy"]
    elif decision["decision"] == "STOP":
        state["status"] = "STOPPED"
        state["pending_interaction"] = None
    else:
        state["status"] = "COMPLETE"
        state["pending_interaction"] = None
        state["session_mode"] = decision["context_strategy"]

    atomic_json(run_path, state)
    response: dict[str, Any] = {
        "ok": True,
        "run_file": str(run_path),
        "decision": decision,
        "run": state,
    }
    root_recommended = root_recommended_command(state)
    if state["status"] == "RUNNING":
        response["terminal"] = False
        response["continuation_required"] = True
        response["next_action"] = {
            "action": (
                "EXECUTE_NEXT_COMMAND"
                if decision["decision"] == "AUTO_ROUTE"
                else "RETRY_CURRENT_COMMAND"
            ),
            "command": state["current_command"],
            "arguments": "--resume" if state["current_command"] == "order.code" else "",
        }
        response["final_response"] = {
            "permitted": False,
            "reason": "NON_TERMINAL_WORKFLOW_STATE",
        }
    else:
        response["terminal"] = True
        response["continuation_required"] = False
        if state["status"] == "STOPPED":
            response["operator_action"] = {
                "action": "START_NEW_WORKFLOW_RUN",
                "recommended_command": root_recommended,
            }
        elif state["status"] in {"PAUSED", "WAITING_OPERATOR"}:
            response["operator_action"] = operator_boundary_action(
                root, run_path, state, route_context=route_context
            )
    if route_context is not None:
        response["route"] = route_context
        command_action = {
            "command": route_context["target"],
            "arguments": route_context["requested_change"],
            "recommended_command": route_context["recommended_command"],
        }
        if decision["decision"] == "AUTO_ROUTE":
            response["next_action"] = {
                "action": "EXECUTE_OWNER_COMMAND",
                **command_action,
            }
        elif decision["decision"] == "STOP":
            response["operator_action"] = {
                "action": "STOP_AUTOMATION_AND_REVIEW_ROUTE",
                **command_action,
            }
    emit(response)
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    try:
        if args.event_file == "-":
            candidate = json.loads(sys.stdin.read())
        else:
            candidate = json.loads(Path(args.event_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return emit_event_rejection(
            run_path,
            state,
            [f"invalid event JSON: {exc}"],
            candidate=None,
        )
    event, errors = validate_event(candidate)
    if errors or event is None:
        return emit_event_rejection(run_path, state, errors, candidate=candidate)
    if event["kind"] == "OPERATOR_INPUT":
        return emit_event_rejection(
            run_path,
            state,
            ["direct OPERATOR_INPUT is forbidden; use workflow_supervisor.py ask"],
            candidate=candidate,
        )
    return evaluate_event(root, run_path, state, config_path, event)


def emit_event_rejection(
    run_path: Path,
    state: dict[str, Any],
    errors: list[str],
    *,
    candidate: Any,
) -> int:
    kind = candidate.get("kind") if isinstance(candidate, dict) else None
    allowed_values: dict[str, Any] = {"kind": sorted(KINDS)}
    if kind in REASONS_BY_KIND:
        allowed_values["reason"] = sorted(REASONS_BY_KIND[kind])
    emit({
        "ok": False,
        "error_code": "CALLER_EVENT_INVALID",
        "action": "CORRECT_EVENT_AND_RETRY",
        "state_mutated": False,
        "terminal": False,
        "continuation_required": True,
        "field_errors": errors,
        "allowed_values": allowed_values,
        "run_file": str(run_path),
        "run": state,
        "next_action": {
            "action": "USE_CANONICAL_EVENT_ADAPTER",
            "adapters": {
                "ADVANCE": "workflow_supervisor.py advance",
                "ROUTE": "workflow_supervisor.py route-feedback",
                "OPERATOR_INPUT": "workflow_supervisor.py ask",
            },
        },
        "final_response": {
            "permitted": False,
            "reason": "NON_TERMINAL_WORKFLOW_STATE",
        },
    })
    return 1


def cmd_ask(args: argparse.Namespace) -> int:
    """Build and apply a canonical OPERATOR_INPUT event."""
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    errors: list[str] = []
    if args.source not in COMMANDS:
        errors.append("source must be a supported OrderSpec command")
    if args.reason not in HARD_OPERATOR_REASONS:
        errors.append(
            "reason must be one of: " + ", ".join(sorted(HARD_OPERATOR_REASONS))
        )
    if args.response_type not in {"choice", "text"}:
        errors.append("response-type must be choice or text")
    if args.resume_strategy not in {"same_session", "fresh_session"}:
        errors.append("resume-strategy must be same_session or fresh_session")
    if args.severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        errors.append("severity must be LOW, MEDIUM, HIGH, or CRITICAL")
    if state["status"] != "RUNNING":
        errors.append(f"run status must be RUNNING, got {state['status']}")
    if args.source != state["current_command"]:
        errors.append(
            f"source {args.source} does not match current command {state['current_command']}"
        )
    if not args.interaction_id.strip():
        errors.append("interaction-id must not be empty")
    if not args.question.strip():
        errors.append("question must not be empty")
    legacy_options = args.option or []
    raw_choices = args.choice or []
    if legacy_options:
        errors.append(
            "choice interactions require --choice <token> <label> <consequence>; --option lacks operator-facing meaning"
        )
    if legacy_options and raw_choices:
        errors.append("--option and --choice cannot be combined")
    options = [choice[0] for choice in raw_choices]
    if args.response_type == "choice":
        if len(options) < 2:
            errors.append("choice interactions require at least two --choice values")
        if len(options) != len(set(options)):
            errors.append("choice interaction options must be unique")
        invalid_options = [
            option for option in options if not re.fullmatch(r"[a-z][a-z0-9_-]*", option)
        ]
        if invalid_options:
            errors.append(
                "choice options must be stable lowercase tokens: " + ", ".join(invalid_options)
            )
    elif options or legacy_options:
        errors.append("text interactions do not accept --choice or --option")
    if errors:
        return emit_event_rejection(run_path, state, errors, candidate={"kind": "OPERATOR_INPUT"})

    interaction: dict[str, Any] = {
        "id": args.interaction_id,
        "kind": args.reason,
        "question": args.question.strip(),
        "response_type": args.response_type,
        "resume_strategy": args.resume_strategy,
    }
    if args.response_type == "choice":
        interaction["options"] = options
        interaction["choices"] = [
            {"value": value, "label": label, "consequence": consequence}
            for value, label, consequence in raw_choices
        ]
    if args.exact_action is not None:
        interaction["exact_action"] = args.exact_action
    event = {
        "version": 1,
        "id": args.event_id or f"OPERATOR-{args.interaction_id}",
        "kind": "OPERATOR_INPUT",
        "reason": args.reason,
        "source": args.source,
        "target": None,
        "severity": args.severity,
        "destructive": args.destructive,
        "summary": args.summary,
        "evidence": args.evidence,
        "interaction": interaction,
    }
    normalized, validation_errors = validate_event(event)
    if validation_errors or normalized is None:
        emit({
            "ok": False,
            "error_code": "FRAMEWORK_ADAPTER_FAILURE",
            "action": "STOP_AND_PRESERVE_EVIDENCE",
            "state_mutated": False,
            "terminal": True,
            "continuation_required": False,
            "field_errors": validation_errors,
            "run_file": str(run_path),
            "run": state,
        })
        return 2
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    return evaluate_event(root, run_path, state, config_path, normalized)


def cmd_advance(args: argparse.Namespace) -> int:
    """Build and apply an ADVANCE event bound to the command that completed."""
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    if not args.source:
        emit({
            "ok": False,
            "action": "ADVANCE_SOURCE_REQUIRED",
            "terminal": False,
            "continuation_required": True,
            "error": "advance requires --source <completed-command>",
            "run_file": str(run_path),
            "run": state,
            "next_action": {
                "action": "EXECUTE_CURRENT_COMMAND",
                "command": state["current_command"],
                "arguments": "--resume" if state["current_command"] == "order.code" else "",
            },
            "final_response": {
                "permitted": False,
                "reason": "NON_TERMINAL_WORKFLOW_STATE",
            },
        })
        return 1
    if args.source != state["current_command"]:
        emit({
            "ok": False,
            "action": "STALE_ADVANCE_REJECTED",
            "terminal": False,
            "continuation_required": True,
            "error": (
                f"completed command {args.source} does not match current command "
                f"{state['current_command']}"
            ),
            "run_file": str(run_path),
            "run": state,
            "next_action": {
                "action": "EXECUTE_CURRENT_COMMAND",
                "command": state["current_command"],
                "arguments": "--resume" if state["current_command"] == "order.code" else "",
            },
            "final_response": {
                "permitted": False,
                "reason": "NON_TERMINAL_WORKFLOW_STATE",
            },
        })
        return 1
    source = state["current_command"]
    target = ADVANCE_TARGETS.get(source)
    if target is None:
        raise ValueError(f"current command {source} has no canonical ADVANCE target")
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    event = {
        "version": 1,
        "id": args.event_id or f"AUTO-ADVANCE-{state['transition_count'] + 1:04d}",
        "kind": "ADVANCE",
        "reason": "STAGE_COMPLETE",
        "source": source,
        "target": target,
        "severity": "LOW",
        "destructive": False,
        "summary": args.summary,
        "evidence": args.evidence,
        "interaction": None,
    }
    normalized, errors = validate_event(event)
    if errors or normalized is None:
        raise ValueError(f"canonical ADVANCE construction failed: {'; '.join(errors)}")
    try:
        return evaluate_event(root, run_path, state, config_path, normalized)
    except ValueError as exc:
        if source != "order.code" or "order.code ADVANCE rejected" not in str(exc):
            raise
        emit({
            "ok": False,
            "action": "ORDER_CODE_INCOMPLETE",
            "terminal": False,
            "continuation_required": True,
            "error": str(exc),
            "run_file": str(run_path),
            "run": state,
            "next_action": {
                "action": "EXECUTE_CURRENT_COMMAND",
                "command": "order.code",
                "arguments": "--resume",
            },
            "final_response": {
                "permitted": False,
                "reason": "NON_TERMINAL_WORKFLOW_STATE",
            },
        })
        return 1


def cmd_route_feedback(args: argparse.Namespace) -> int:
    """Build and apply the canonical ROUTE event from persistent feedback."""
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    feedback_path = resolve_feedback_path(root, state, args.feedback_file)
    feedback = read_report(feedback_path)
    if feedback.get("status") != "open":
        raise ValueError(f"feedback {feedback.get('id')} is not open")
    requested_change = feedback.get("requested_change")
    if not isinstance(requested_change, str) or not requested_change.strip():
        raise ValueError("feedback requested_change must be a non-empty string")
    event = {
        "version": 1,
        "id": feedback["id"],
        "kind": "ROUTE",
        "reason": (
            "IMPLEMENTATION_REPAIR"
            if feedback.get("category") == "implementation_repair"
            else "UPSTREAM_DEFECT"
        ),
        "source": feedback["source"],
        "target": feedback["target"],
        "severity": None,
        "destructive": False,
        "summary": feedback.get("summary", ""),
        "evidence": feedback["evidence"],
        "interaction": None,
    }
    normalized, errors = validate_event(event)
    if errors or normalized is None:
        raise ValueError(f"canonical ROUTE construction failed: {'; '.join(errors)}")
    route_context = {
        "feedback_id": feedback["id"],
        "feedback_file": str(feedback_path),
        "target": feedback["target"],
        "requested_change": requested_change.strip(),
        "recommended_command": recommended_command(feedback["target"], requested_change),
    }
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    return evaluate_event(
        root,
        run_path,
        state,
        config_path,
        normalized,
        route_context=route_context,
    )


def cmd_answer(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    pending = state.get("pending_interaction")
    answer_error = None
    if state["status"] != "WAITING_OPERATOR" or not isinstance(pending, dict):
        raise ValueError("run is not waiting for operator input")
    if pending.get("id") != args.interaction_id:
        answer_error = f"pending interaction is {pending.get('id')}, not {args.interaction_id}"
    elif not args.answer.strip():
        answer_error = "answer must not be empty"
    elif pending.get("response_type", "choice") == "choice" and args.answer not in pending.get("options", []):
        answer_error = f"answer must be one of: {', '.join(pending.get('options', []))}"
    if answer_error is not None:
        emit({
            "ok": False,
            "error_code": "INVALID_OPERATOR_ANSWER",
            "error": answer_error,
            "state_mutated": False,
            "terminal": True,
            "continuation_required": False,
            "run_file": str(run_path),
            "run": state,
            "operator_action": operator_boundary_action(root, run_path, state),
        })
        return 1
    timestamp = now()
    state["status"] = "RUNNING"
    state["updated_at"] = timestamp
    state["pending_interaction"] = None
    state["resume_input"] = {
        "interaction_id": args.interaction_id,
        "answer": args.answer,
        "resume_strategy": pending.get("resume_strategy", "same_session"),
    }
    state["session_mode"] = "resume" if pending.get("resume_strategy", "same_session") == "same_session" else "fresh"
    state["history"].append({
        "at": timestamp,
        "type": "OPERATOR_ANSWER",
        "interaction_id": args.interaction_id,
        "answer": args.answer,
    })
    atomic_json(run_path, state)
    emit({
        "ok": True,
        "run_file": str(run_path),
        "run": state,
        "terminal": False,
        "continuation_required": True,
        "next_action": {
            "action": "RESUME_CURRENT_COMMAND_WITH_OPERATOR_INPUT",
            "command": state["current_command"],
            "arguments": "--resume" if state["current_command"] == "order.code" else "",
            "resume_input": state["resume_input"],
        },
        "final_response": {
            "permitted": False,
            "reason": "NON_TERMINAL_WORKFLOW_STATE",
        },
    })
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    payload: dict[str, Any] = {"ok": True, "run_file": str(run_path), "run": state}
    root_command = initial_command(state) or state["current_command"]
    root_arguments = "--resume" if root_command == "order.code" else ""
    recommended = f"/{root_command}" + (f" {root_arguments}" if root_arguments else "")
    if state["status"] == "RUNNING":
        current_arguments = "--resume" if state["current_command"] == "order.code" else ""
        payload["terminal"] = False
        payload["continuation_required"] = True
        payload["next_action"] = {
            "action": "EXECUTE_CURRENT_COMMAND",
            "command": state["current_command"],
            "arguments": current_arguments,
        }
        payload["final_response"] = {
            "permitted": False,
            "reason": "NON_TERMINAL_WORKFLOW_STATE",
        }
        if args.operator_recovery:
            payload["operator_action"] = {
                "action": "RESUME_WORKFLOW_AFTER_HOST_INTERRUPTION",
                "recommended_command": recommended,
            }
    elif state["status"] == "STOPPED":
        payload["terminal"] = True
        payload["continuation_required"] = False
        payload["operator_action"] = {
            "action": "START_NEW_WORKFLOW_RUN",
            "recommended_command": recommended,
        }
    elif state["status"] in {"PAUSED", "WAITING_OPERATOR"}:
        payload["terminal"] = state["status"] in {"PAUSED", "WAITING_OPERATOR", "COMPLETE"}
        payload["continuation_required"] = False
        payload["operator_action"] = operator_boundary_action(root, run_path, state)
    else:
        payload["terminal"] = True
        payload["continuation_required"] = False
    emit(payload)
    return 0


def cmd_guard_final(args: argparse.Namespace) -> int:
    """Fail closed when an agent tries to end a non-terminal workflow turn."""
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    if state["status"] == "RUNNING":
        current_arguments = "--resume" if state["current_command"] == "order.code" else ""
        emit({
            "ok": False,
            "action": "CONTINUE_REQUIRED",
            "terminal": False,
            "continuation_required": True,
            "run_file": str(run_path),
            "run": state,
            "next_action": {
                "action": "EXECUTE_CURRENT_COMMAND",
                "command": state["current_command"],
                "arguments": current_arguments,
            },
            "final_response": {
                "permitted": False,
                "reason": "NON_TERMINAL_WORKFLOW_STATE",
            },
        })
        return 1
    emit({
        "ok": True,
        "action": "FINAL_RESPONSE_PERMITTED",
        "terminal": True,
        "continuation_required": False,
        "run_file": str(run_path),
        "run": state,
        "final_response": {"permitted": True},
    })
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    if state["status"] != "PAUSED":
        raise ValueError(f"cannot resume run while status is {state['status']}")
    if not args.reason.strip():
        raise ValueError("resume reason must not be empty")
    event = latest_boundary_event(state)
    applied_transition = None
    if isinstance(event, dict) and event.get("source") == state["current_command"]:
        kind = event.get("kind")
        source = event.get("source")
        target = event.get("target")
        legal = (
            kind == "ROUTE" and target in ROUTE_TARGETS.get(source, set())
        ) or (
            kind == "ADVANCE" and ADVANCE_TARGETS.get(source) == target
        )
        if kind in {"ROUTE", "ADVANCE"} and not legal:
            raise ValueError(f"cannot resume illegal pending {kind} transition {source} -> {target}")
        if legal:
            state["current_command"] = target
            state["transition_count"] += 1
            if kind == "ROUTE":
                state["route_count"] += 1
            applied_transition = {
                "event_id": event.get("id"),
                "kind": kind,
                "source": source,
                "target": target,
            }
    timestamp = now()
    state["status"] = "RUNNING"
    state["updated_at"] = timestamp
    state["session_mode"] = args.session_mode
    history_item = {
        "at": timestamp,
        "type": "OPERATOR_RESUME",
        "reason": args.reason,
        "session_mode": args.session_mode,
    }
    if applied_transition is not None:
        history_item["applied_transition"] = applied_transition
    state["history"].append(history_item)
    atomic_json(run_path, state)
    emit({
        "ok": True,
        "run_file": str(run_path),
        "run": state,
        "terminal": False,
        "continuation_required": True,
        "next_action": {
            "action": "EXECUTE_CURRENT_COMMAND",
            "command": state["current_command"],
            "arguments": "--resume" if state["current_command"] == "order.code" else "",
        },
        "final_response": {
            "permitted": False,
            "reason": "NON_TERMINAL_WORKFLOW_STATE",
        },
    })
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OrderSpec continuous workflow supervisor state")
    parser.add_argument("-C", "--project-root", default=".")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    start = sub.add_parser("start")
    start.add_argument("--feature-dir")
    start.add_argument("--command", required=True)
    start.add_argument("--terminal-command", default="order.code-check", choices=sorted(TERMINAL_COMMANDS))
    start.add_argument("--config")
    start.set_defaults(handler=cmd_start)

    acquire = sub.add_parser("acquire")
    acquire.add_argument("--feature-dir")
    acquire.add_argument("--command", required=True)
    acquire.add_argument("--terminal-command", default="order.code-check", choices=sorted(TERMINAL_COMMANDS))
    acquire.add_argument("--config")
    acquire.set_defaults(handler=cmd_acquire)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--run-file", required=True)
    evaluate.add_argument("--event-file", required=True, help="JSON file or - for stdin")
    evaluate.add_argument("--config")
    evaluate.set_defaults(handler=cmd_evaluate)

    ask = sub.add_parser("ask", help="Build and apply a canonical OPERATOR_INPUT event")
    ask.add_argument("--run-file", required=True)
    ask.add_argument("--source", required=True)
    ask.add_argument("--reason", required=True)
    ask.add_argument("--interaction-id", required=True)
    ask.add_argument("--question", required=True)
    ask.add_argument("--response-type", default="choice")
    ask.add_argument("--option", action="append")
    ask.add_argument(
        "--choice",
        action="append",
        nargs=3,
        metavar=("TOKEN", "LABEL", "CONSEQUENCE"),
    )
    ask.add_argument("--exact-action")
    ask.add_argument("--resume-strategy", default="same_session")
    ask.add_argument("--event-id")
    ask.add_argument("--summary", default="")
    ask.add_argument("--evidence", default="")
    ask.add_argument("--severity", default="HIGH")
    ask.add_argument("--destructive", action="store_true")
    ask.add_argument("--config")
    ask.set_defaults(handler=cmd_ask)

    advance = sub.add_parser("advance", help="Build and apply the canonical ADVANCE event")
    advance.add_argument("--run-file", required=True)
    advance.add_argument("--source", choices=sorted(COMMANDS))
    advance.add_argument("--event-id")
    advance.add_argument("--summary", default="")
    advance.add_argument("--evidence", default="")
    advance.add_argument("--config")
    advance.set_defaults(handler=cmd_advance)

    route_feedback = sub.add_parser(
        "route-feedback", help="Build and apply the canonical ROUTE event from feedback"
    )
    route_feedback.add_argument("--run-file", required=True)
    route_feedback.add_argument("--feedback-file", required=True)
    route_feedback.add_argument("--config")
    route_feedback.set_defaults(handler=cmd_route_feedback)

    answer = sub.add_parser("answer")
    answer.add_argument("--run-file", required=True)
    answer.add_argument("--interaction-id", required=True)
    answer.add_argument("--answer", required=True)
    answer.set_defaults(handler=cmd_answer)

    status = sub.add_parser("status")
    status.add_argument("--run-file", required=True)
    status.add_argument(
        "--operator-recovery",
        action="store_true",
        help="include the exact recovery command for an already interrupted host turn",
    )
    status.set_defaults(handler=cmd_status)

    guard_final = sub.add_parser(
        "guard-final", help="Reject a final response while the workflow is non-terminal"
    )
    guard_final.add_argument("--run-file", required=True)
    guard_final.set_defaults(handler=cmd_guard_final)

    resume = sub.add_parser("resume")
    resume.add_argument("--run-file", required=True)
    resume.add_argument("--reason", required=True)
    resume.add_argument("--session-mode", choices=["fresh", "resume"], default="fresh")
    resume.set_defaults(handler=cmd_resume)

    args = parser.parse_args()
    try:
        if args.subcommand in {"start", "acquire"} and args.command not in COMMANDS:
            raise ValueError("--command must be a supported OrderSpec command")
        return args.handler(args)
    except (OSError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
