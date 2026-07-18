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
import sys
import tempfile
from pathlib import Path
from typing import Any

from automation_policy import (
    CONFIG_PATH,
    classify,
    load_valid_config,
    load_valid_event,
)


RUN_ID_RE = re.compile(r"^RUN-[0-9]{3}$")
STATUSES = {"RUNNING", "WAITING_OPERATOR", "PAUSED", "STOPPED", "COMPLETE"}


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


def next_run_id(store: Path) -> str:
    numbers: list[int] = []
    for path in store.glob("RUN-*.json"):
        if RUN_ID_RE.fullmatch(path.stem):
            numbers.append(int(path.stem.split("-")[1]))
    return f"RUN-{max(numbers, default=0) + 1:03d}"


def load_state(path: Path) -> dict[str, Any]:
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
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"run state missing fields: {missing}")
    if data.get("version") != 1 or not RUN_ID_RE.fullmatch(str(data.get("id", ""))):
        raise ValueError("invalid run state version or id")
    if data.get("status") not in STATUSES:
        raise ValueError("invalid run status")
    if not isinstance(data.get("history"), list):
        raise ValueError("run history must be an array")
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


def cmd_start(args: argparse.Namespace) -> int:
    root = safe_project_root(args.project_root)
    feature = safe_feature_dir(root, args.feature_dir)
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    config = load_valid_config(config_path)
    store = run_store(root, feature)
    run_id = next_run_id(store)
    timestamp = now()
    state = {
        "version": 1,
        "id": run_id,
        "status": "RUNNING",
        "project_root": str(root),
        "feature_dir": str(feature) if feature else None,
        "current_command": args.command,
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
    path = store / f"{run_id}.json"
    atomic_json(path, state)
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
    state = load_state(run_path)
    if state["status"] not in {"RUNNING", "PAUSED"}:
        raise ValueError(f"cannot evaluate event while run status is {state['status']}")
    config_path = Path(args.config).resolve() if args.config else root / CONFIG_PATH
    config = load_valid_config(config_path)
    event = load_valid_event(args.event_file)
    if event["source"] != state["current_command"]:
        raise ValueError(
            f"event source {event['source']} does not match current command {state['current_command']}"
        )
    decision = classify(config, event, counters_for(state))
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
    state = load_state(run_path)
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
    emit({"ok": True, "run_file": str(run_path), "run": load_state(run_path)})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OrderSpec continuous workflow supervisor state")
    parser.add_argument("-C", "--project-root", default=".")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    start = sub.add_parser("start")
    start.add_argument("--feature-dir")
    start.add_argument("--command", required=True)
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

    args = parser.parse_args()
    try:
        if args.subcommand == "start" and not re.fullmatch(r"order\.[a-z][a-z0-9-]*", args.command):
            raise ValueError("--command must be an order.* command")
        return args.handler(args)
    except (OSError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
