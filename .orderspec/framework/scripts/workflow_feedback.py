#!/usr/bin/env python3
"""Persistent typed handoffs between OrderSpec pipeline commands.

Code execution records an owner-targeted defect before it stops. Authoring
commands list their own open handoffs and consume them only after repair.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

TARGETS = {"order.bootstrap", "order.spec", "order.plan", "order.tasks"}
SOURCES = TARGETS | {"order.code", "order.code-check", "order.tasks-check", "order.plan-check", "order.spec-check"}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def safe_feature_dir(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_dir() or ".orderspec" not in path.parts or "features" not in path.parts:
        raise ValueError("feature directory must be an existing .orderspec/features directory")
    return path


def store_dir(feature_dir: Path) -> Path:
    return feature_dir / ".state" / "feedback"


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


def read_all(feature_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    result = []
    for path in sorted(store_dir(feature_dir).glob("FB-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid feedback report {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"invalid feedback report {path}: expected object")
        if (
            value.get("version") != 1
            or value.get("id") != path.stem
            or value.get("status") not in {"open", "consumed"}
            or value.get("source") not in SOURCES
            or value.get("target") not in TARGETS
        ):
            raise ValueError(f"invalid feedback report shape: {path}")
        result.append((path, value))
    return result


def next_id(feature_dir: Path) -> str:
    numbers = []
    for path, _ in read_all(feature_dir):
        try:
            numbers.append(int(path.stem.split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"FB-{max(numbers, default=0) + 1:03d}"


def cmd_create(args: argparse.Namespace) -> int:
    try:
        feature_dir = safe_feature_dir(args.feature_dir)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    values: dict[str, Any] = {}
    if args.input_file:
        try:
            raw = sys.stdin.read() if args.input_file == "-" else Path(args.input_file).read_text(encoding="utf-8")
            loaded = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            emit({"ok": False, "error": f"cannot read feedback input: {exc}"})
            return 2
        if not isinstance(loaded, dict):
            emit({"ok": False, "error": "feedback input must be a JSON object"})
            return 2
        values = loaded
    source = values.get("source", args.source)
    target = values.get("target", args.target)
    category = values.get("category", args.category)
    summary = values.get("summary", args.summary)
    evidence = values.get("evidence", args.evidence)
    location = values.get("location", args.location or "")
    requested_change = values.get("requested_change", args.requested_change)
    if source not in SOURCES or target not in TARGETS:
        emit({"ok": False, "error": "invalid source or target"})
        return 2
    required = {"category": category, "summary": summary, "evidence": evidence, "requested_change": requested_change}
    if any(not isinstance(value, str) or not value.strip() for value in required.values()):
        emit({"ok": False, "error": "category, summary, evidence, and requested_change are required strings"})
        return 2
    if not isinstance(location, str):
        emit({"ok": False, "error": "location must be a string"})
        return 2
    try:
        feedback_id = next_id(feature_dir)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    payload = {
        "version": 1,
        "id": feedback_id,
        "status": "open",
        "created_at": now(),
        "source": source,
        "target": target,
        "category": category.strip(),
        "summary": summary.strip(),
        "evidence": evidence.strip(),
        "location": location,
        "requested_change": requested_change.strip(),
        "recommended_command": f'/{target} "{requested_change.strip()}"',
    }
    path = store_dir(feature_dir) / f"{feedback_id}.json"
    atomic_json(path, payload)
    emit({"ok": True, "report": str(path), "feedback": payload})
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    try:
        feature_dir = safe_feature_dir(args.feature_dir)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    items = []
    try:
        reports = read_all(feature_dir)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    for path, item in reports:
        if args.target and item.get("target") != args.target:
            continue
        if not args.all and item.get("status") != "open":
            continue
        items.append({**item, "report": str(path)})
    emit({"ok": True, "count": len(items), "feedback": items})
    return 0


def cmd_consume(args: argparse.Namespace) -> int:
    try:
        feature_dir = safe_feature_dir(args.feature_dir)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    path = store_dir(feature_dir) / f"{args.id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": f"cannot read feedback {args.id}: {exc}"})
        return 2
    if payload.get("status") == "consumed":
        emit({"ok": True, "feedback": payload, "already_consumed": True})
        return 0
    if payload.get("target") != args.consumer:
        emit({"ok": False, "error": f"feedback target is {payload.get('target')}, not {args.consumer}"})
        return 2
    payload.update({"status": "consumed", "consumed_at": now(), "consumed_by": args.consumer})
    atomic_json(path, payload)
    emit({"ok": True, "feedback": payload})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OrderSpec cross-stage feedback reports")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--feature-dir", required=True)
    create.add_argument("--input-file", help="read report fields from a JSON object; use - for stdin")
    create.add_argument("--source", choices=sorted(SOURCES))
    create.add_argument("--target", choices=sorted(TARGETS))
    create.add_argument("--category")
    create.add_argument("--summary")
    create.add_argument("--evidence")
    create.add_argument("--location", default="")
    create.add_argument("--requested-change")
    create.set_defaults(handler=cmd_create)
    listing = sub.add_parser("list")
    listing.add_argument("--feature-dir", required=True)
    listing.add_argument("--target", choices=sorted(TARGETS))
    listing.add_argument("--all", action="store_true")
    listing.set_defaults(handler=cmd_list)
    consume = sub.add_parser("consume")
    consume.add_argument("--feature-dir", required=True)
    consume.add_argument("--id", required=True)
    consume.add_argument("--consumer", required=True, choices=sorted(TARGETS))
    consume.set_defaults(handler=cmd_consume)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
