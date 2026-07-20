#!/usr/bin/env python3
"""Persistent typed handoffs between OrderSpec pipeline commands.

Any pipeline command records an earlier-owner defect before a routed stop.
Owner commands receive open feature and project handoffs through command
context and consume them only after validated repair.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

TARGETS = {"order.bootstrap", "order.spec", "order.plan", "order.tasks"}
SOURCES = TARGETS | {
    "order.feature", "order.code-to-spec", "order.code", "order.code-check",
    "order.tasks-check", "order.plan-check", "order.spec-check",
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def safe_feature_dir(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_dir() or ".orderspec" not in path.parts or "features" not in path.parts:
        raise ValueError("feature directory must be an existing .orderspec/features directory")
    return path


def feature_store_dir(feature_dir: Path) -> Path:
    return feature_dir / ".state" / "feedback"


def safe_project_root(value: str) -> Path:
    root = Path(value).resolve()
    if not (root / ".orderspec").is_dir():
        raise ValueError("project root must contain .orderspec")
    return root


def project_store_dir(project_root: Path) -> Path:
    return project_root / ".orderspec" / "state" / "feedback"


def resolve_store(
    *, feature_dir_value: str | None, project_root_value: str, scope: str
) -> tuple[Path, str, str]:
    if scope == "project":
        return project_store_dir(safe_project_root(project_root_value)), "PFB", "project"
    if not feature_dir_value:
        raise ValueError("--feature-dir is required for feature-scoped feedback")
    return feature_store_dir(safe_feature_dir(feature_dir_value)), "FB", "feature"


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


def read_report(path: Path) -> dict[str, Any]:
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
    return value


def read_all(store: Path, prefix: str) -> list[tuple[Path, dict[str, Any]]]:
    return [(path, read_report(path)) for path in sorted(store.glob(f"{prefix}-*.json"))]


def next_id(store: Path, prefix: str) -> str:
    numbers = []
    for path, _ in read_all(store, prefix):
        try:
            numbers.append(int(path.stem.split("-")[1]))
        except (IndexError, ValueError):
            pass
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def feedback_fingerprint(values: dict[str, Any]) -> str:
    identity = {
        key: str(values.get(key, "")).strip()
        for key in ("source", "target", "category", "summary", "evidence", "location", "requested_change")
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]


def recommended_command(target: str, requested_change: str) -> str:
    """Return a copy-pasteable slash command without lossy quote handling."""
    return f"/{target} {json.dumps(requested_change.strip(), ensure_ascii=False)}"


def load_open_for_command(
    project_root: Path,
    feature_dir: Path | None,
    target: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load project and feature handoffs without making malformed state fatal."""
    stores = [(project_store_dir(project_root), "PFB")]
    if feature_dir is not None:
        stores.append((feature_store_dir(feature_dir), "FB"))
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for store, prefix in stores:
        for path in sorted(store.glob(f"{prefix}-*.json")):
            try:
                item = read_report(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if item.get("status") == "open" and item.get("target") == target:
                items.append({**item, "report": str(path)})
    return items, errors


def cmd_create(args: argparse.Namespace) -> int:
    try:
        store, prefix, scope = resolve_store(
            feature_dir_value=args.feature_dir,
            project_root_value=args.project_root,
            scope=args.scope,
        )
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
        fingerprint = feedback_fingerprint({
            "source": source,
            "target": target,
            "category": category,
            "summary": summary,
            "evidence": evidence,
            "location": location,
            "requested_change": requested_change,
        })
        for existing_path, existing in read_all(store, prefix):
            if existing.get("status") == "open" and existing.get("fingerprint") == fingerprint:
                emit({
                    "ok": True,
                    "created": False,
                    "report": str(existing_path),
                    "feedback": existing,
                })
                return 0
        feedback_id = next_id(store, prefix)
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    payload = {
        "version": 1,
        "id": feedback_id,
        "scope": scope,
        "status": "open",
        "created_at": now(),
        "source": source,
        "target": target,
        "category": category.strip(),
        "summary": summary.strip(),
        "evidence": evidence.strip(),
        "location": location,
        "requested_change": requested_change.strip(),
        "fingerprint": fingerprint,
        "recommended_command": recommended_command(target, requested_change),
    }
    path = store / f"{feedback_id}.json"
    atomic_json(path, payload)
    emit({"ok": True, "created": True, "report": str(path), "feedback": payload})
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    try:
        store, prefix, _ = resolve_store(
            feature_dir_value=args.feature_dir,
            project_root_value=args.project_root,
            scope=args.scope,
        )
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    items = []
    try:
        reports = read_all(store, prefix)
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
        store, _, _ = resolve_store(
            feature_dir_value=args.feature_dir,
            project_root_value=args.project_root,
            scope=args.scope,
        )
    except ValueError as exc:
        emit({"ok": False, "error": str(exc)})
        return 2
    path = store / f"{args.id}.json"
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
    create.add_argument("--feature-dir")
    create.add_argument("--project-root", default=".")
    create.add_argument("--scope", choices=["feature", "project"], default="feature")
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
    listing.add_argument("--feature-dir")
    listing.add_argument("--project-root", default=".")
    listing.add_argument("--scope", choices=["feature", "project"], default="feature")
    listing.add_argument("--target", choices=sorted(TARGETS))
    listing.add_argument("--all", action="store_true")
    listing.set_defaults(handler=cmd_list)
    consume = sub.add_parser("consume")
    consume.add_argument("--feature-dir")
    consume.add_argument("--project-root", default=".")
    consume.add_argument("--scope", choices=["feature", "project"], default="feature")
    consume.add_argument("--id", required=True)
    consume.add_argument("--consumer", required=True, choices=sorted(TARGETS))
    consume.set_defaults(handler=cmd_consume)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
