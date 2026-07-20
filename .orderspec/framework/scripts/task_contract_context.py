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
from task_context import read_context_block  # noqa: E402
from task_progress import parse_tasks  # noqa: E402
from trace_constants import SPEC_PREFIXES  # noqa: E402


ID_RE = re.compile(
    r"(?:[A-Z][A-Z0-9-]*:)?(?P<id>"
    r"(?:" + "|".join(SPEC_PREFIXES) + r")-\d{3})"
)
ANCHOR_RE = re.compile(
    r"^\s*-\s+\*\*(?P<id>"
    r"(?:" + "|".join(SPEC_PREFIXES) + r")-\d{3})\*\*:"
)
MODEL_ANCHOR_RE = re.compile(
    r"^###\s+(?P<kind>Entity|Structure|Value Set)\s+"
    r"(?P<id>(?:ENT|STR|VAL)-\d{3}):\s+(?P<name>\S.*)$"
)
MODEL_PREFIX_BY_KIND = {"Entity": "ENT", "Structure": "STR", "Value Set": "VAL"}


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


def task_context_refs(tasks_path: Path, task_id: str) -> list[str]:
    payload, _ = read_context_block(tasks_path)
    if not isinstance(payload, dict):
        return []
    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        return []
    entry = tasks.get(task_id)
    if not isinstance(entry, dict):
        return []
    refs = entry.get("contract_refs", [])
    if not isinstance(refs, list):
        return []
    return [value for value in refs if isinstance(value, str)]


def load_spec_blocks(spec_path: Path) -> dict[str, str]:
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    anchors: list[tuple[str, int, int]] = []
    for index, line in enumerate(lines):
        match = ANCHOR_RE.match(line)
        if match:
            anchors.append((match.group("id"), index, 2))
            continue
        model_match = MODEL_ANCHOR_RE.match(line)
        if model_match:
            anchors.append((model_match.group("id"), index, 3))

    blocks: dict[str, str] = {}
    anchor_starts = {start for _, start, _ in anchors}
    for spec_id, start, boundary_level in anchors:
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if index in anchor_starts:
                end = index
                break
            heading = re.match(r"^(#{2,6})\s+", lines[index])
            if heading and len(heading.group(1)) <= boundary_level:
                end = index
                break
        block = "\n".join(lines[start:end]).strip()
        if block:
            blocks[spec_id] = block
    return blocks


def contract_anchor_errors(spec_path: Path) -> list[str]:
    """Validate context-addressable anchors without making them coverage IDs."""
    seen: dict[str, int] = {}
    errors: list[str] = []
    for line_number, line in enumerate(spec_path.read_text(encoding="utf-8").splitlines(), start=1):
        model_heading = re.match(r"^###\s+(?:Entity|Structure|Value Set)\b", line)
        model_match = MODEL_ANCHOR_RE.match(line)
        if model_heading and not model_match:
            errors.append(
                f"Information Model heading at line {line_number} requires kind-specific stable ID: {line.strip()}"
            )
            continue
        match = ANCHOR_RE.match(line) or model_match
        if not match:
            continue
        contract_id = match.group("id")
        if contract_id in seen:
            errors.append(
                f"duplicate contract context ID {contract_id} at lines {seen[contract_id]} and {line_number}"
            )
        else:
            seen[contract_id] = line_number
        if "kind" in match.groupdict():
            expected = MODEL_PREFIX_BY_KIND[match.group("kind")]
            if not contract_id.startswith(f"{expected}-"):
                errors.append(
                    f"{match.group('kind')} at line {line_number} must use {expected}-NNN, got {contract_id}"
                )
    return errors


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

    coverage_refs = task_refs(record["line"])
    extra_refs = task_context_refs(tasks_path, task_id)
    refs = list(dict.fromkeys([*coverage_refs, *extra_refs]))
    anchor_errors = contract_anchor_errors(spec_path)
    if anchor_errors:
        return 2, {
            "ok": False,
            "error": "invalid_contract_anchors",
            "task_id": task_id,
            "validation_errors": anchor_errors,
        }
    spec_blocks = load_spec_blocks(spec_path)
    mechanisms = load_mechanisms(mechanisms_path)

    missing_refs = [spec_id for spec_id in refs if spec_id not in spec_blocks]
    missing_mechanisms = [
        spec_id for spec_id in coverage_refs if spec_id not in mechanisms
    ]

    payload = {
        "ok": not missing_refs and not missing_mechanisms,
        "task_id": task_id,
        "task_line": record["line"],
        "refs": refs,
        "coverage_refs": coverage_refs,
        "contract_refs": extra_refs,
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
