#!/usr/bin/env python3
"""Resolve deterministic contract context for one implementation task.

The task-context block controls source-file access. This resolver supplies the
small, inline contract excerpts a worker needs for referenced spec IDs without
granting the worker repository-wide Markdown access.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import get_repo_root  # noqa: E402
from task_progress import parse_tasks  # noqa: E402


ID_RE = re.compile(
    r"(?:[A-Z][A-Z0-9-]*:)?(?P<id>"
    r"(?:REQ|NFR|SC|INV|EDGE|UJ|AC|Q|ASM|DEC|IF|CON)-\d{3})"
)
ANCHOR_RE = re.compile(
    r"^\s*-\s+\*\*(?P<id>"
    r"(?:REQ|NFR|SC|INV|EDGE|UJ|AC|Q|ASM|DEC|IF|CON)-\d{3})\*\*:"
)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def normalize_feature_dir(value: str, repo_root: Path) -> Path:
    feature_dir = Path(value).expanduser().resolve()
    try:
        feature_dir.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("feature directory must be inside repository root") from exc
    return feature_dir


def task_refs(task_line: str) -> list[str]:
    parts = task_line.split(" | ")
    if len(parts) < 3:
        return []
    refs = parts[2].strip()
    if not refs:
        return []

    result: list[str] = []
    for match in ID_RE.finditer(refs):
        value = match.group("id")
        if value not in result:
            result.append(value)
    return result


def load_spec_blocks(spec_path: Path) -> dict[str, str]:
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    anchors: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        match = ANCHOR_RE.match(line)
        if match:
            anchors.append((match.group("id"), index))

    blocks: dict[str, str] = {}
    for position, (spec_id, start) in enumerate(anchors):
        end = anchors[position + 1][1] if position + 1 < len(anchors) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        if block:
            blocks[spec_id] = block
    return blocks


def load_mechanisms(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}

    result: dict[str, dict[str, str]] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    rows = csv.DictReader(lines, delimiter="\t")
    for row in rows:
        spec_id = row.get("spec_id", "").strip()
        if spec_id:
            result[spec_id] = {
                key: (value or "").strip()
                for key, value in row.items()
                if key is not None
            }
    return result


def phase_context(tasks_path: Path, task_line_number: int) -> list[str]:
    lines = tasks_path.read_text(encoding="utf-8").splitlines()
    start = max(0, task_line_number - 1)
    phase_start = 0
    for index in range(start, -1, -1):
        if lines[index].startswith("## "):
            phase_start = index
            break

    phase_end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            phase_end = index
            break

    selected: list[str] = []
    for line in lines[phase_start:phase_end]:
        stripped = line.strip()
        if stripped.startswith("**Goal**:") or stripped.startswith("**Verification**:"):
            selected.append(stripped)
    return selected


def resolve(feature_dir: Path, task_id: str, repo_root: Path) -> tuple[int, dict[str, Any]]:
    tasks_path = feature_dir / "tasks.md"
    spec_path = feature_dir / "spec.md"
    mechanisms_path = feature_dir / ".state" / "mechanisms.tsv"

    records, errors = parse_tasks(tasks_path)
    if errors:
        return 2, {
            "ok": False,
            "error": "invalid_tasks_file",
            "task_id": task_id,
            "validation_errors": errors,
        }

    record = next((item for item in records if item["task_id"] == task_id), None)
    if record is None:
        return 2, {
            "ok": False,
            "error": "task_not_found",
            "task_id": task_id,
            "validation_errors": [f"task not found: {task_id}"],
        }

    if not spec_path.is_file():
        return 2, {
            "ok": False,
            "error": "missing_spec",
            "task_id": task_id,
            "validation_errors": [f"spec.md not found: {spec_path}"],
        }

    refs = task_refs(record["line"])
    spec_blocks = load_spec_blocks(spec_path)
    mechanisms = load_mechanisms(mechanisms_path)

    missing_refs = [spec_id for spec_id in refs if spec_id not in spec_blocks]
    missing_mechanisms = [spec_id for spec_id in refs if spec_id not in mechanisms]

    payload = {
        "ok": not missing_refs and not missing_mechanisms,
        "task_id": task_id,
        "task_line": record["line"],
        "refs": refs,
        "phase_context": phase_context(tasks_path, record["line_number"]),
        "spec_excerpts": [
            {
                "id": spec_id,
                "path": str(spec_path.relative_to(repo_root)).replace("\\", "/"),
                "excerpt": spec_blocks[spec_id],
            }
            for spec_id in refs
            if spec_id in spec_blocks
        ],
        "mechanisms": [mechanisms[spec_id] for spec_id in refs if spec_id in mechanisms],
        "missing_refs": missing_refs,
        "missing_mechanisms": missing_mechanisms,
    }

    if "[US" in record["line"] and not payload["phase_context"]:
        payload["ok"] = False
        payload["error"] = "missing_phase_context"
        payload["validation_errors"] = [
            f"task {task_id} is a story task but its phase has no Goal/Verification context"
        ]
        return 2, payload

    if missing_refs:
        payload["error"] = "missing_spec_ids"
        payload["validation_errors"] = [
            f"task {task_id} references undefined spec IDs: {', '.join(missing_refs)}"
        ]
        return 2, payload

    if missing_mechanisms:
        payload["error"] = "missing_mechanisms"
        payload["validation_errors"] = [
            f"task {task_id} has no mechanisms.tsv rows for spec IDs: {', '.join(missing_mechanisms)}"
        ]
        return 2, payload

    return 0, payload


def validate(feature_dir: Path, repo_root: Path) -> tuple[int, dict[str, Any]]:
    tasks_path = feature_dir / "tasks.md"
    records, errors = parse_tasks(tasks_path)
    if errors:
        return 2, {"ok": False, "error": "invalid_tasks_file", "validation_errors": errors}

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for record in records:
        rc, payload = resolve(feature_dir, record["task_id"], repo_root)
        results.append(
            {
                "task_id": record["task_id"],
                "ok": payload.get("ok", False),
                "refs": payload.get("refs", []),
                "missing_refs": payload.get("missing_refs", []),
            }
        )
        if rc != 0:
            failures.append(payload)

    return (2 if failures else 0), {
        "ok": not failures,
        "total": len(records),
        "failures": failures,
        "tasks": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="task_contract_context.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("resolve", "validate"):
        command = subparsers.add_parser(name)
        command.add_argument("--feature-dir", required=True)
        command.add_argument("--task-id")
        command.add_argument("--json", action="store_true")

    args = parser.parse_args()
    repo_root = get_repo_root().resolve()
    try:
        feature_dir = normalize_feature_dir(args.feature_dir, repo_root)
    except ValueError as exc:
        emit({"ok": False, "error": "invalid_feature_dir", "message": str(exc)})
        return 2

    if args.command == "resolve":
        if not args.task_id:
            emit({"ok": False, "error": "missing_task_id", "message": "--task-id is required"})
            return 2
        rc, payload = resolve(feature_dir, args.task_id, repo_root)
    else:
        rc, payload = validate(feature_dir, repo_root)

    emit(payload)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
