#!/usr/bin/env python3
"""Build deterministic whole-contract obligation ledgers for /order.code-check."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from common import get_repo_root  # noqa: E402
from task_contract_context import load_mechanisms, load_spec_blocks, task_refs  # noqa: E402
from task_progress import parse_tasks  # noqa: E402


OBLIGATION_PREFIXES = {"REQ", "NFR", "SC", "INV", "EDGE", "IF", "AC"}
ANCHOR_RE = re.compile(r"^\s*-\s+\*\*(?P<id>[A-Z]+-\d{3})\*\*:")
PRIORITY_RE = re.compile(r"Priority:\s*(P\d+)", re.IGNORECASE)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def normalize_feature_dir(value: str, repo_root: Path) -> Path:
    feature_dir = Path(value).expanduser().resolve()
    try:
        feature_dir.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError("feature directory must be inside repository root") from exc
    return feature_dir


def anchor_metadata(spec_path: Path) -> dict[str, dict[str, str]]:
    section = ""
    priority = ""
    result: dict[str, dict[str, str]] = {}
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            priority = ""
        elif line.startswith("### "):
            section = line[4:].strip()
            match = PRIORITY_RE.search(line)
            if match:
                priority = match.group(1).upper()
        match = ANCHOR_RE.match(line)
        if not match:
            continue
        spec_id = match.group("id")
        inline_priority = PRIORITY_RE.search(line)
        if spec_id.startswith("UJ-") and inline_priority:
            priority = inline_priority.group(1).upper()
        result[spec_id] = {"section": section, "priority": priority or "unspecified"}
    return result


def task_evidence(tasks_path: Path) -> dict[str, list[dict[str, Any]]]:
    if not tasks_path.is_file():
        return {}
    records, errors = parse_tasks(tasks_path)
    if errors:
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for spec_id in task_refs(record["line"]):
            result.setdefault(spec_id, []).append(
                {
                    "task_id": record["task_id"],
                    "path": record["path"],
                    "completed": record["status"] in {"x", "X"},
                    "phase": record["phase"],
                }
            )
    return result


def build(feature_dir: Path, repo_root: Path) -> tuple[int, dict[str, Any]]:
    spec_path = feature_dir / "spec.md"
    if not spec_path.is_file():
        return 2, {
            "ok": False,
            "error": "missing_spec",
            "message": f"spec.md not found: {spec_path}",
        }
    blocks = load_spec_blocks(spec_path)
    metadata = anchor_metadata(spec_path)
    mechanisms = load_mechanisms(feature_dir / ".state" / "mechanisms.tsv")
    tasks = task_evidence(feature_dir / "tasks.md")

    obligations = []
    for spec_id, excerpt in blocks.items():
        if spec_id.split("-", 1)[0] not in OBLIGATION_PREFIXES:
            continue
        mechanism = mechanisms.get(spec_id)
        declared_paths = []
        if mechanism:
            raw_paths = mechanism.get("primary_files", "")
            declared_paths = [value.strip() for value in raw_paths.split(",") if value.strip()]
        task_paths = [item["path"] for item in tasks.get(spec_id, [])]
        evidence_paths = list(dict.fromkeys([*declared_paths, *task_paths]))
        obligations.append(
            {
                "id": spec_id,
                "kind": spec_id.split("-", 1)[0],
                "priority": metadata.get(spec_id, {}).get("priority", "unspecified"),
                "section": metadata.get(spec_id, {}).get("section", ""),
                "excerpt": excerpt,
                "mechanism": mechanism,
                "tasks": tasks.get(spec_id, []),
                "evidence_paths": evidence_paths,
            }
        )
    return 0, {
        "ok": True,
        "feature_dir": str(feature_dir),
        "spec": str(spec_path.relative_to(repo_root)),
        "count": len(obligations),
        "obligation_ids": [item["id"] for item in obligations],
        "obligations": obligations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="code_obligations.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "packet"):
        command = subparsers.add_parser(name)
        command.add_argument("--feature-dir", required=True)
        command.add_argument("--json", action="store_true")
        if name == "packet":
            command.add_argument("--obligation", required=True)
    build_parser = subparsers.add_parser("write-ledger")
    build_parser.add_argument("--feature-dir", required=True)
    build_parser.add_argument("--output", required=True)
    build_parser.add_argument("--json", action="store_true")
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--ledger", required=True)
    record_parser.add_argument("--result-file", required=True)
    record_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "record":
        ledger_path = Path(args.ledger).expanduser().resolve()
        results_path = ledger_path.with_name("code-obligation-results.json")
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            result = json.loads(Path(args.result_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            emit({"ok": False, "error": "invalid_input", "message": str(exc)})
            return 2
        obligation_ids = ledger.get("obligation_ids", [])
        if not isinstance(result, dict) or result.get("obligation") not in obligation_ids:
            emit({"ok": False, "error": "unknown_obligation_result"})
            return 2
        if result.get("result") not in {"SATISFIED", "VIOLATED", "UNPROVEN", "NOT_CHECKED"}:
            emit({"ok": False, "error": "invalid_result"})
            return 2
        if not isinstance(result.get("evidence"), list) or not result["evidence"] or not all(
            isinstance(item, str) for item in result["evidence"]
        ):
            emit({"ok": False, "error": "invalid_evidence", "message": "evidence must be a non-empty string array"})
            return 2
        if not isinstance(result.get("implementation_paths"), list) or not all(
            isinstance(item, str) for item in result["implementation_paths"]
        ):
            emit({"ok": False, "error": "invalid_implementation_paths"})
            return 2
        try:
            stored = json.loads(results_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = {"ledger_ids": obligation_ids, "results": {}}
        if stored.get("ledger_ids") != obligation_ids or not isinstance(stored.get("results"), dict):
            emit({"ok": False, "error": "results_ledger_mismatch"})
            return 2
        if result["obligation"] in stored["results"]:
            emit({"ok": False, "error": "duplicate_obligation_result", "obligation": result["obligation"]})
            return 2
        stored["results"][result["obligation"]] = result
        results_path.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        emit({
            "ok": True,
            "output": str(results_path),
            "recorded": result["obligation"],
            "assessed": len(stored["results"]),
            "total": len(obligation_ids),
            "complete": len(stored["results"]) == len(obligation_ids),
        })
        return 0

    repo_root = get_repo_root().resolve()
    try:
        feature_dir = normalize_feature_dir(args.feature_dir, repo_root)
    except ValueError as exc:
        emit({"ok": False, "error": "invalid_feature_dir", "message": str(exc)})
        return 2
    rc, payload = build(feature_dir, repo_root)
    if rc != 0:
        emit(payload)
        return rc
    if args.command == "packet":
        obligation = next(
            (item for item in payload["obligations"] if item["id"] == args.obligation),
            None,
        )
        if obligation is None:
            emit({"ok": False, "error": "unknown_obligation", "obligation": args.obligation})
            return 2
        payload = {
            "ok": True,
            "feature_dir": str(feature_dir),
            "obligation": obligation,
            "inspection_paths": obligation["evidence_paths"],
            "result_schema": {
                "obligation": obligation["id"],
                "result": "SATISFIED|VIOLATED|UNPROVEN|NOT_CHECKED",
                "evidence": [],
                "implementation_paths": [],
                "finding": None,
            },
        }
    elif args.command == "write-ledger":
        output = Path(args.output).expanduser().resolve()
        try:
            output.relative_to(feature_dir)
        except ValueError:
            emit({"ok": False, "error": "unsafe_output", "message": "ledger output must be inside feature directory"})
            return 2
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results_output = output.with_name("code-obligation-results.json")
        results_output.write_text(
            json.dumps(
                {"ledger_ids": payload["obligation_ids"], "results": {}},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        payload = {
            "ok": True,
            "output": str(output),
            "results_output": str(results_output),
            "count": payload["count"],
        }
    emit(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
