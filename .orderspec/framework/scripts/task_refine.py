#!/usr/bin/env python3
"""Transactional guard for surgical /order.tasks refinement.

`begin` stores the exact pre-refine file and protected completed-task state.
`validate` rejects loss or mutation of completed work and restores the original
tasks.md automatically when validation fails.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from task_context import CONTEXT_CLOSE, CONTEXT_OPEN, read_context_block
from task_progress import TASK_LINE_RE, atomic_replace, parse_tasks


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_completed(path: Path) -> tuple[dict[str, str], dict[str, Any], list[str]]:
    records, errors = parse_tasks(path)
    context, context_errors = read_context_block(path)
    errors.extend(context_errors)
    completed: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = TASK_LINE_RE.match(line)
            if match and match.group("status") in {"x", "X"}:
                completed[match.group("task")] = line
    except OSError as exc:
        errors.append(f"cannot read tasks file: {exc}")
    entries = context.get("tasks", {}) if isinstance(context, dict) else {}
    completed_context = {task_id: entries.get(task_id) for task_id in completed}
    return completed, completed_context, errors


def cmd_begin(args: argparse.Namespace) -> int:
    tasks = Path(args.tasks)
    snapshot = Path(args.snapshot)
    try:
        raw = tasks.read_bytes()
    except OSError as exc:
        emit({"ok": False, "error": f"cannot read tasks.md: {exc}"})
        return 2
    completed, completed_context, errors = load_completed(tasks)
    payload = {
        "version": 1,
        "tasks_path": str(tasks),
        "sha256": digest(raw),
        "content_base64": base64.b64encode(raw).decode("ascii"),
        "completed_lines": completed,
        "completed_context": completed_context,
    }
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{snapshot.name}.", dir=str(snapshot.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, snapshot)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    emit(
        {
            "ok": True,
            "snapshot": str(snapshot),
            "protected_completed": sorted(completed),
            "preexisting_validation_errors": errors,
        }
    )
    return 0


def restore(tasks: Path, snapshot: dict[str, Any]) -> None:
    raw = base64.b64decode(snapshot["content_base64"], validate=True)
    atomic_replace(tasks, raw.decode("utf-8"))


def replace_context_block(content: str, payload: dict[str, Any]) -> str:
    lines = content.splitlines(keepends=True)
    opens = [index for index, line in enumerate(lines) if line.strip() == CONTEXT_OPEN]
    closes = [index for index, line in enumerate(lines) if line.strip() == CONTEXT_CLOSE]
    if len(opens) != 1 or len(closes) != 1 or closes[0] <= opens[0]:
        raise ValueError("tasks.md must contain one closed task-context block")
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return "".join(lines[: opens[0] + 1]) + rendered + "".join(lines[closes[0] :])


def cmd_resequence_pending(args: argparse.Namespace) -> int:
    """Create deterministic numeric gaps without changing completed task IDs."""
    tasks = Path(args.tasks)
    snapshot_path = Path(args.snapshot)
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if Path(str(snapshot.get("tasks_path", ""))).resolve() != tasks.resolve():
            raise ValueError("snapshot belongs to a different tasks file")
        records, errors = parse_tasks(tasks)
        context, context_errors = read_context_block(tasks)
        errors.extend(context_errors)
        if errors or not isinstance(context, dict) or not isinstance(context.get("tasks"), dict):
            raise ValueError("; ".join(errors) or "invalid task-context")
        seen_pending = False
        for record in records:
            if record["status"] == " ":
                seen_pending = True
            elif seen_pending:
                raise ValueError("completed tasks must form a prefix before pending resequencing")
        pending = [record for record in records if record["status"] == " "]
        completed_numbers = [
            int(record["task_id"][1:]) for record in records if record["status"] in {"x", "X"}
        ]
        start = ((max(completed_numbers, default=-10) // 10) + 2) * 10 if completed_numbers else 10
        assigned = [start + index * 10 for index in range(len(pending))]
        if assigned and assigned[-1] > 999:
            raise ValueError("pending task resequencing exceeds T999")
        mapping = {
            record["task_id"]: f"T{number:03d}" for record, number in zip(pending, assigned)
        }
        entries = context["tasks"]
        if set(entries) != {record["task_id"] for record in records}:
            raise ValueError("task-context keys do not match task lines")
        updated_entries: dict[str, Any] = {}
        for task_id, entry in entries.items():
            updated_entries[mapping.get(task_id, task_id)] = entry
        context["tasks"] = updated_entries
        content = tasks.read_text(encoding="utf-8")
        rewritten: list[str] = []
        for line in content.splitlines(keepends=True):
            match = TASK_LINE_RE.match(line.rstrip("\r\n"))
            if match and match.group("task") in mapping:
                old = match.group("task")
                offset = line.index(old)
                line = line[:offset] + mapping[old] + line[offset + len(old):]
            rewritten.append(line)
        updated = replace_context_block("".join(rewritten), context)
        atomic_replace(tasks, updated)
        free_before = f"T{start - 10:03d}" if pending and start >= 20 else None
        emit({
            "ok": True,
            "action": "PENDING_TASKS_RESEQUENCED",
            "terminal": False,
            "continuation_required": True,
            "mapping": mapping,
            "free_id_before_first_pending": free_before,
            "next_action": "apply the bounded Refine patch, then run all validation steps",
        })
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit({
            "ok": False,
            "action": "STOP",
            "terminal": True,
            "continuation_required": False,
            "error": "pending_resequence_failed",
            "details": str(exc),
            "operator_action": {
                "action": "RESET_AND_REGENERATE_WORK_ORDER",
                "recommended_command": "/order.code --reset",
            },
        })
        return 2


def cmd_validate(args: argparse.Namespace) -> int:
    tasks = Path(args.tasks)
    snapshot_path = Path(args.snapshot)
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": f"cannot read snapshot: {exc}"})
        return 2

    if Path(str(snapshot.get("tasks_path", ""))).resolve() != tasks.resolve():
        emit({"ok": False, "error": "snapshot belongs to a different tasks file"})
        return 2

    completed, completed_context, errors = load_completed(tasks)
    protected_lines = snapshot.get("completed_lines", {})
    protected_context = snapshot.get("completed_context", {})
    for task_id, original_line in protected_lines.items():
        if completed.get(task_id) != original_line:
            errors.append(f"completed task {task_id} was removed, unchecked, or changed")
        if (
            protected_context.get(task_id) is not None
            and completed_context.get(task_id) != protected_context.get(task_id)
        ):
            errors.append(f"completed task {task_id} task-context changed")

    if errors:
        try:
            restore(tasks, snapshot)
            restored = True
        except Exception as exc:  # exact recovery failure must be visible
            errors.append(f"automatic restore failed: {exc}")
            restored = False
        if restored:
            emit({
                "ok": False,
                "action": "REFINE_RESTORED_RETRY",
                "terminal": False,
                "continuation_required": True,
                "error": "unsafe_refine",
                "details": errors,
                "restored": True,
                "next_action": "begin a new bounded Refine attempt and correct the rejected candidate",
            })
        else:
            emit({
                "ok": False,
                "action": "STOP",
                "terminal": True,
                "continuation_required": False,
                "error": "unsafe_refine",
                "details": errors,
                "restored": False,
                "operator_action": {
                    "action": "RESET_AND_REGENERATE_WORK_ORDER",
                    "recommended_command": "/order.code --reset",
                },
            })
        return 1

    emit(
        {
            "ok": True,
            "tasks": str(tasks),
            "protected_completed": sorted(protected_lines),
            "before_sha256": snapshot.get("sha256"),
            "after_sha256": digest(tasks.read_bytes()),
        }
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard surgical tasks.md refinement")
    sub = parser.add_subparsers(dest="command", required=True)
    begin = sub.add_parser("begin")
    begin.add_argument("--tasks", required=True)
    begin.add_argument("--snapshot", required=True)
    begin.set_defaults(handler=cmd_begin)
    validate = sub.add_parser("validate")
    validate.add_argument("--tasks", required=True)
    validate.add_argument("--snapshot", required=True)
    validate.set_defaults(handler=cmd_validate)
    resequence = sub.add_parser("resequence-pending")
    resequence.add_argument("--tasks", required=True)
    resequence.add_argument("--snapshot", required=True)
    resequence.set_defaults(handler=cmd_resequence_pending)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
