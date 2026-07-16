#!/usr/bin/env python3
"""Resolve and validate deterministic per-task file context.

The task-context block in a feature's tasks.md is the declaration. This
script is the only consumer used by command prompts and emits the worker's
read whitelist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import get_repo_root  # noqa: E402
from task_progress import parse_tasks  # noqa: E402
from trace_parse import _parse_pathmanifest  # noqa: E402


CONTEXT_OPEN = "```task-context"
CONTEXT_CLOSE = "```"
CONTEXT_VERSION = 1
GLOB_CHARS = set("*?[]")


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def normalize_feature_dir(value: str, repo_root: Path) -> Path:
    feature_dir = Path(value).expanduser().resolve()
    try:
        feature_dir.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("feature directory must be inside repository root") from exc
    return feature_dir


def safe_relative_path(value: str) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if value.startswith("./") or "\\" in value or "\x00" in value:
        return False
    if any(char in GLOB_CHARS for char in value):
        return False
    path = Path(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and path.as_posix() == value
    )


def inside_repository(path: Path, repo_root: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    return True


def read_context_block(tasks_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return None, [f"cannot read tasks file: {exc}"]

    blocks: list[list[str]] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() != CONTEXT_OPEN:
            index += 1
            continue
        index += 1
        block: list[str] = []
        while index < len(lines) and lines[index].strip() != CONTEXT_CLOSE:
            block.append(lines[index])
            index += 1
        if index == len(lines):
            return None, ["task-context fence is not closed"]
        blocks.append(block)
        index += 1

    if len(blocks) != 1:
        return None, [f"tasks.md must contain exactly one task-context block; found {len(blocks)}"]

    try:
        value = json.loads("\n".join(blocks[0]))
    except json.JSONDecodeError as exc:
        return None, [f"task-context is invalid JSON: {exc}"]
    if not isinstance(value, dict):
        return None, ["task-context must be a JSON object"]
    return value, []


def validate_payload(
    payload: Any,
    records: list[dict[str, Any]],
    repo_root: Path,
    pathmanifest: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    missing_required: list[str] = []
    if not isinstance(payload, dict):
        return {}, ["task-context must be a JSON object"], missing_required

    if set(payload) != {"version", "tasks"}:
        errors.append("task-context must contain only version and tasks")

    if payload.get("version") != CONTEXT_VERSION:
        errors.append(f"task-context version must be {CONTEXT_VERSION}")

    task_entries = payload.get("tasks")
    if not isinstance(task_entries, dict):
        return {}, errors + ["task-context.tasks must be an object"], missing_required

    task_ids = {record["task_id"] for record in records}
    entry_ids = set(task_entries)
    for task_id in sorted(task_ids - entry_ids):
        errors.append(f"task {task_id} has no task-context entry")
    for task_id in sorted(entry_ids - task_ids):
        errors.append(f"task-context has orphan entry {task_id}")

    normalized: dict[str, dict[str, Any]] = {}
    for task_id in sorted(entry_ids & task_ids):
        entry = task_entries[task_id]
        if not isinstance(entry, dict):
            errors.append(f"task {task_id} context must be an object")
            continue
        if set(entry) != {"read", "target_state"}:
            errors.append(f"task {task_id} context must contain only read and target_state")
            continue
        target_state = entry.get("target_state")
        if target_state not in {"new", "mod", "del"}:
            errors.append(f"task {task_id} target_state must be new, mod, or del")
            continue
        read_paths = entry.get("read")
        if not isinstance(read_paths, list) or not all(isinstance(path, str) for path in read_paths):
            errors.append(f"task {task_id} context read must be an array of strings")
            continue
        if len(read_paths) != len(set(read_paths)):
            errors.append(f"task {task_id} context read contains duplicate paths")
        if any(not safe_relative_path(path) for path in read_paths):
            errors.append(f"task {task_id} context read contains an unsafe path")

        record = next(record for record in records if record["task_id"] == task_id)
        task_path = record["path"]
        manifest_tag = pathmanifest.get(task_path)
        expected_state = {"[NEW]": "new", "[MOD]": "mod", "[DEL]": "del"}.get(manifest_tag)
        if expected_state is None:
            errors.append(f"task {task_id} path is absent from plan.md pathmanifest: {task_path}")
        elif target_state != expected_state:
            errors.append(
                f"task {task_id} target_state {target_state!r} disagrees with plan.md {manifest_tag}: {task_path}"
            )
        prior_writer = any(
            prior["path"] == task_path and prior["line_number"] < record["line_number"]
            for prior in records
        )
        if target_state in {"mod", "del"} and task_path not in read_paths:
            errors.append(f"task {task_id} write target is not in read whitelist: {task_path}")

        for path in read_paths:
            if path.lower().endswith(".md") and path != task_path:
                errors.append(f"task {task_id} may read Markdown only when it is its write target: {path}")
            absolute = repo_root / path
            if not inside_repository(absolute, repo_root):
                errors.append(f"task {task_id} read path escapes repository: {path}")
                continue
            if not absolute.is_file():
                if (
                    target_state == "new"
                    and path == task_path
                    and prior_writer
                ):
                    continue
                if target_state == "del" and path == task_path and record["status"] in {"x", "X"}:
                    continue
                missing_required.append(path)
                errors.append(f"task {task_id} read file does not exist: {path}")

        normalized[task_id] = {"read": read_paths, "target_state": target_state}

    return normalized, errors, sorted(set(missing_required))


def load_and_validate(
    feature_dir: Path,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str], list[str]]:
    tasks_path = feature_dir / "tasks.md"
    pathmanifest, plan_errors = _parse_pathmanifest(feature_dir / "plan.md")
    records, task_errors = parse_tasks(tasks_path)
    payload, block_errors = read_context_block(tasks_path)
    errors = [*task_errors, *plan_errors, *block_errors]
    if payload is None:
        return records, {}, errors, []
    normalized, payload_errors, missing_required = validate_payload(
        payload, records, repo_root, pathmanifest
    )
    return records, normalized, [*errors, *payload_errors], missing_required


def cmd_validate(args: argparse.Namespace) -> int:
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = normalize_feature_dir(args.feature_dir, repo_root)
    except ValueError as exc:
        emit({"ok": False, "error": "invalid_feature_dir", "message": str(exc)})
        return 2

    records, _, errors, missing_required = load_and_validate(feature_dir, repo_root)
    if errors:
        emit(
            {
                "ok": False,
                "error": "invalid_task_context",
                "tasks_file": str(feature_dir / "tasks.md"),
                "validation_errors": errors,
                "missing_required": missing_required,
            }
        )
        return 2

    emit(
        {
            "ok": True,
            "tasks_file": str(feature_dir / "tasks.md"),
            "total": len(records),
            "task_ids": [record["task_id"] for record in records],
        }
    )
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = normalize_feature_dir(args.feature_dir, repo_root)
    except ValueError as exc:
        emit({"ok": False, "error": "invalid_feature_dir", "message": str(exc)})
        return 2

    records, contexts, errors, missing_required = load_and_validate(feature_dir, repo_root)
    record = next((item for item in records if item["task_id"] == args.task_id), None)
    if record is None:
        errors.append(f"task not found: {args.task_id}")

    if errors:
        emit(
            {
                "ok": False,
                "error": "invalid_task_context",
                "tasks_file": str(feature_dir / "tasks.md"),
                "task_id": args.task_id,
                "validation_errors": errors,
                "missing_required": missing_required,
            }
        )
        return 2

    assert record is not None
    read_paths = contexts[args.task_id]["read"]
    emit(
        {
            "ok": True,
            "task_id": record["task_id"],
            "status": "X" if record["status"] in {"x", "X"} else " ",
            "task_line": record["line"],
            "write_paths": [record["path"]],
            "to_read": [
                {
                    "path": path,
                    "usage": "inspect",
                    "authority": "feature",
                    "required": True,
                }
                for path in read_paths
            ],
            "missing_required": [],
        }
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="task_context.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate task-context data")
    validate.add_argument("--feature-dir", required=True)
    validate.add_argument("--json", action="store_true", help="emit JSON output (default)")
    validate.set_defaults(handler=cmd_validate)

    resolve = subparsers.add_parser("resolve", help="resolve one task's read whitelist")
    resolve.add_argument("--feature-dir", required=True)
    resolve.add_argument("--task-id", required=True)
    resolve.add_argument("--json", action="store_true", help="emit JSON output (default)")
    resolve.set_defaults(handler=cmd_resolve)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
