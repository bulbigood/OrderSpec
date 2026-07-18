#!/usr/bin/env python3
"""Persistent runtime-neutral supervisor state for OrderSpec automation.

Runtime adapters submit typed events after an agent command finishes or asks a
question. The supervisor classifies the event, advances or pauses the run, and
persists enough state to resume after an operator answer or process failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any

from frontmatter import extract_yaml_frontmatter

from automation_policy import (
    ADVANCE_TARGETS,
    COMMANDS,
    CONFIG_PATH,
    ROUTE_TARGETS,
    TERMINAL_COMMANDS,
    classify,
    load_valid_config,
    load_valid_event,
)


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


def cmd_start(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    feature = safe_feature_dir(root, args.feature_dir)
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    config = load_valid_config(config_path)
    store = run_store(root, feature)
    timestamp = now()
    state = {
        "version": 1,
        "id": "",
        "status": "RUNNING",
        "project_root": str(root),
        "feature_dir": str(feature) if feature else None,
        "current_command": args.command,
        "terminal_command": args.terminal_command,
        "created_at": timestamp,
        "updated_at": timestamp,
        "transition_count": 0,
        "route_count": 0,
        "decision_counts": {},
        "event_counts": {},
        "pending_interaction": None,
        "resume_input": None,
        "session_mode": config["context"]["between_commands"],
        "history": [{"at": timestamp, "type": "RUN_STARTED", "command": args.command}],
    }
    path = create_run(store, state)
    emit({"ok": True, "run_file": str(path), "run": state})
    return 0


def counters_for(state: dict[str, Any]) -> dict[str, int]:
    counters = {
        "transitions": state["transition_count"],
        "routes": state["route_count"],
    }
    counters.update({f"rule:{key}": value for key, value in state["decision_counts"].items()})
    counters.update({f"event:{key}": value for key, value in state["event_counts"].items()})
    return counters


def cmd_evaluate(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    if state["status"] != "RUNNING":
        raise ValueError(f"cannot evaluate event while run status is {state['status']}")
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    config = load_valid_config(config_path)
    event = load_valid_event(args.event_file)
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
    emit({"ok": True, "run_file": str(run_path), "decision": decision, "run": state})
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    pending = state.get("pending_interaction")
    if state["status"] != "WAITING_OPERATOR" or not isinstance(pending, dict):
        raise ValueError("run is not waiting for operator input")
    if pending.get("id") != args.interaction_id:
        raise ValueError(f"pending interaction is {pending.get('id')}, not {args.interaction_id}")
    if not args.answer.strip():
        raise ValueError("answer must not be empty")
    if pending.get("response_type", "choice") == "choice" and args.answer not in pending.get("options", []):
        raise ValueError(f"answer must be one of: {', '.join(pending.get('options', []))}")
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
    emit({"ok": True, "run_file": str(run_path), "run": state})
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    emit({"ok": True, "run_file": str(run_path), "run": load_state(run_path, root)})
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    run_path = resolve_run_path(root, args.run_file)
    state = load_state(run_path, root)
    if state["status"] != "PAUSED":
        raise ValueError(f"cannot resume run while status is {state['status']}")
    if not args.reason.strip():
        raise ValueError("resume reason must not be empty")
    timestamp = now()
    state["status"] = "RUNNING"
    state["updated_at"] = timestamp
    state["session_mode"] = args.session_mode
    state["history"].append({
        "at": timestamp,
        "type": "OPERATOR_RESUME",
        "reason": args.reason,
        "session_mode": args.session_mode,
    })
    atomic_json(run_path, state)
    emit({"ok": True, "run_file": str(run_path), "run": state})
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

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--run-file", required=True)
    evaluate.add_argument("--event-file", required=True, help="JSON file or - for stdin")
    evaluate.add_argument("--config")
    evaluate.set_defaults(handler=cmd_evaluate)

    answer = sub.add_parser("answer")
    answer.add_argument("--run-file", required=True)
    answer.add_argument("--interaction-id", required=True)
    answer.add_argument("--answer", required=True)
    answer.set_defaults(handler=cmd_answer)

    status = sub.add_parser("status")
    status.add_argument("--run-file", required=True)
    status.set_defaults(handler=cmd_status)

    resume = sub.add_parser("resume")
    resume.add_argument("--run-file", required=True)
    resume.add_argument("--reason", required=True)
    resume.add_argument("--session-mode", choices=["fresh", "resume"], default="fresh")
    resume.set_defaults(handler=cmd_resume)

    args = parser.parse_args()
    try:
        if args.subcommand == "start" and args.command not in COMMANDS:
            raise ValueError("--command must be a supported OrderSpec command")
        return args.handler(args)
    except (OSError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
