#!/usr/bin/env python3
"""Deterministic task state checks and completion marking for /order.code.

The coordinator owns worker result interpretation. This script owns the narrow
state transition from one unchecked task to `[X]` after a successful result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


TASK_LINE_RE = re.compile(r"^- \[(?P<status>[ xX])\] (?P<task>T\d{3})(?P<rest>.*)$")
TASK_ID_RE = re.compile(r"^T\d{3}$")
SUCCESS_STATUSES = {"PASS", "NOT_RUN"}
VERIFICATION_WORDS_RE = re.compile(
    r"\b(?:gate|test|tests|verify|verification|checkpoint|run)\b", re.IGNORECASE
)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def fail(message: str, *, code: str = "invalid_task_state", rc: int = 2) -> int:
    emit({"ok": False, "error": code, "message": message})
    return rc


def safe_relative_path(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and value == value.strip()


def parse_tasks(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        return [], [f"cannot read tasks file: {exc}"]

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    previous_number = -1

    for line_number, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")
        match = TASK_LINE_RE.match(line)
        if not match:
            continue

        task_id = match.group("task")
        parts = line.split(" | ")
        if len(parts) < 3:
            errors.append(f"line {line_number}: task {task_id} needs a path field")
            continue

        task_path = parts[1].strip()
        if not task_path or not safe_relative_path(task_path):
            errors.append(f"line {line_number}: task {task_id} has unsafe or empty path")

        number = int(task_id[1:])
        if task_id in seen:
            errors.append(f"line {line_number}: duplicate task id {task_id}")
        if number < previous_number:
            errors.append(f"line {line_number}: task ids are out of order at {task_id}")
        seen.add(task_id)
        previous_number = max(previous_number, number)

        records.append(
            {
                "task_id": task_id,
                "status": match.group("status"),
                "path": task_path,
                "line_number": line_number,
                "line": line,
                "requires_verification": bool(VERIFICATION_WORDS_RE.search(parts[-1])),
            }
        )

    if not records:
        errors.append("no task lines found")

    return records, errors


def cmd_validate(args: argparse.Namespace) -> int:
    records, errors = parse_tasks(Path(args.tasks))
    if errors:
        return fail("; ".join(errors), code="invalid_tasks_file")

    incomplete = [record["task_id"] for record in records if record["status"] == " "]
    emit(
        {
            "ok": True,
            "tasks_file": args.tasks,
            "total": len(records),
            "completed": len(records) - len(incomplete),
            "unchecked": len(incomplete),
            "first_unchecked": incomplete[0] if incomplete else None,
        }
    )
    return 0


def load_result(args: argparse.Namespace) -> tuple[dict[str, Any] | None, str | None]:
    try:
        if args.result_file:
            raw = Path(args.result_file).read_text(encoding="utf-8")
        else:
            raw = sys.stdin.read()
        result = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid worker result JSON: {exc}"

    if not isinstance(result, dict):
        return None, "worker result must be a JSON object"
    return result, None


def validate_success_result(result: dict[str, Any], record: dict[str, Any]) -> str | None:
    if result.get("task_id") != record["task_id"]:
        return "worker result task_id does not match target task"
    if result.get("status") != "SUCCESS":
        return f"worker result status is {result.get('status')!r}, expected SUCCESS"

    changed_files = result.get("changed_files")
    if not isinstance(changed_files, list) or not all(isinstance(item, str) for item in changed_files):
        return "worker result changed_files must be a list of strings"
    for changed in changed_files:
        if changed != record["path"]:
            return f"worker changed forbidden path: {changed} (allowed: {record['path']})"

    verification = result.get("verification")
    if not isinstance(verification, dict):
        return "worker result verification must be an object"
    verification_status = verification.get("status")
    if verification_status not in SUCCESS_STATUSES:
        return f"worker verification status is {verification_status!r}"
    if record["requires_verification"] and verification_status != "PASS":
        return "task requires verification but worker reported NOT_RUN"
    evidence = verification.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        return "worker result verification evidence is empty"

    deviation = result.get("deviation")
    if deviation not in (None, ""):
        return "worker result contains a deviation; coordinator must route it before marking"

    return None


def atomic_replace(path: Path, content: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def cmd_mark(args: argparse.Namespace) -> int:
    tasks_path = Path(args.tasks)
    records, errors = parse_tasks(tasks_path)
    if errors:
        return fail("; ".join(errors), code="invalid_tasks_file")

    result, result_error = load_result(args)
    if result_error:
        return fail(result_error, code="invalid_worker_result")
    assert result is not None

    task_id = result.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id):
        return fail("worker result has invalid task_id", code="invalid_worker_result")

    record = next((item for item in records if item["task_id"] == task_id), None)
    if record is None:
        return fail(f"task not found: {task_id}", code="task_not_found")
    if record["status"] in {"x", "X"}:
        return fail(f"task already marked [X]: {task_id}", code="task_already_complete")

    validation_error = validate_success_result(result, record)
    if validation_error:
        return fail(validation_error, code="worker_result_rejected")

    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        return fail(f"cannot reread tasks file: {exc}", code="tasks_read_failed")

    index = record["line_number"] - 1
    original = lines[index]
    prefix = original[: original.index("[")]
    suffix_start = original.index("]") + 1
    lines[index] = f"{prefix}[X]{original[suffix_start:]}"

    try:
        atomic_replace(tasks_path, "".join(lines))
    except OSError as exc:
        return fail(f"cannot atomically mark {task_id}: {exc}", code="tasks_write_failed")

    emit(
        {
            "ok": True,
            "task_id": task_id,
            "status": "X",
            "tasks_file": args.tasks,
            "line_number": record["line_number"],
        }
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="task_progress.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate task lines and report completion state")
    validate.add_argument("--tasks", required=True)
    validate.set_defaults(handler=cmd_validate)

    mark = subparsers.add_parser("mark", help="mark one successful task [X] from worker JSON")
    mark.add_argument("--tasks", required=True)
    mark.add_argument("--result-file", help="read worker JSON from file; stdin is used when omitted")
    mark.set_defaults(handler=cmd_mark)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
