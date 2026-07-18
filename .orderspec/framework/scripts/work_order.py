#!/usr/bin/env python3
"""Capture and safely roll back one tasks.md work order.

Git is used only as an immutable object database. The script never invokes a
Git write command. Rollback is restricted to the frozen plan pathmanifest and
clears task checkboxes only after every path was restored successfully.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from common import get_repo_root
from task_progress import atomic_replace, parse_tasks
from trace_parse import _parse_pathmanifest

BASELINE_NAME = "work-order-baseline.json"


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=not binary, check=False
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace") if binary else result.stderr
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return result.stdout


def safe_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and path.as_posix() == value


def ensure_contained(root: Path, path: Path) -> None:
    """Reject a parent symlink that would redirect a planned write outside Git root."""
    try:
        path.parent.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"planned path parent escapes repository: {path}") from exc


def resolve_inputs(feature_value: str) -> tuple[Path, Path, Path, Path]:
    root = get_repo_root().resolve()
    feature = Path(feature_value).resolve()
    try:
        feature.relative_to(root)
    except ValueError as exc:
        raise ValueError("feature directory must be inside repository root") from exc
    plan = feature / "plan.md"
    tasks = feature / "tasks.md"
    if not plan.is_file() or not tasks.is_file():
        raise ValueError("feature must contain plan.md and tasks.md")
    return root, feature, plan, tasks


def baseline_path(feature: Path) -> Path:
    return feature / ".state" / BASELINE_NAME


def atomic_payload(path: Path, payload: dict[str, Any]) -> None:
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


def tracked_entry(root: Path, path: str) -> tuple[str, str]:
    output = git(root, "ls-files", "--stage", "--", path)
    lines = [line for line in str(output).splitlines() if line]
    if len(lines) != 1:
        raise ValueError(f"baseline [MOD]/[DEL] path must be tracked exactly once: {path}")
    match = re.match(r"^(\d{6}) ([0-9a-f]+) 0\t", lines[0])
    if not match or match.group(1) not in {"100644", "100755", "120000"}:
        raise ValueError(f"unsupported Git entry for {path}: {lines[0]}")
    return match.group(1), match.group(2)


def cmd_capture(args: argparse.Namespace) -> int:
    try:
        root, feature, plan, tasks = resolve_inputs(args.feature_dir)
        manifest, errors = _parse_pathmanifest(plan)
        if errors:
            raise ValueError("; ".join(errors))
        if not manifest or any(not safe_path(path) for path in manifest):
            raise ValueError("pathmanifest is empty or contains unsafe paths")
        records, task_errors = parse_tasks(tasks)
        if task_errors:
            raise ValueError("; ".join(task_errors))
        if any(item["status"] in {"x", "X"} for item in records):
            raise ValueError("cannot capture baseline after task execution started")
        git_root = Path(str(git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
        if git_root != root:
            raise ValueError(f"OrderSpec root {root} differs from Git root {git_root}")
        paths = sorted(manifest)
        status = str(git(root, "status", "--porcelain=v1", "--untracked-files=all", "--", *paths))
        if status.strip():
            raise ValueError(f"planned paths must be clean before baseline capture: {status.strip()}")
        entries = []
        for rel in paths:
            absolute = root / rel
            ensure_contained(root, absolute)
            tag = manifest[rel]
            if tag == "[NEW]":
                if absolute.exists() or absolute.is_symlink():
                    raise ValueError(f"[NEW] path exists at baseline: {rel}")
                entries.append({"path": rel, "state": "new", "mode": None, "blob": None})
            else:
                mode, blob = tracked_entry(root, rel)
                entries.append(
                    {"path": rel, "state": "mod" if tag == "[MOD]" else "del", "mode": mode, "blob": blob}
                )
        target = baseline_path(feature)
        if target.exists() and not args.replace:
            raise ValueError(f"baseline already exists: {target}; use --replace only for a new clean work order")
        payload = {
            "version": 1,
            "git_head": str(git(root, "rev-parse", "HEAD")).strip(),
            "plan_sha256": sha256(plan),
            "tasks_path": str(tasks.relative_to(root)),
            "entries": entries,
        }
        atomic_payload(target, payload)
        emit({"ok": True, "baseline": str(target), "paths": len(entries), "git_head": payload["git_head"]})
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


def load_baseline(feature: Path, plan: Path) -> dict[str, Any]:
    path = baseline_path(feature)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"work-order baseline unavailable: {exc}") from exc
    if payload.get("version") != 1 or not isinstance(payload.get("entries"), list):
        raise ValueError("invalid work-order baseline")
    if payload.get("plan_sha256") != sha256(plan):
        raise ValueError("plan.md changed after baseline capture; automatic rollback is unsafe")
    return payload


def current_kind(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_file():
        return "file"
    if path.exists():
        return "other"
    return "absent"


def actions_for(root: Path, payload: dict[str, Any]) -> list[dict[str, str]]:
    actions = []
    for entry in payload["entries"]:
        rel = entry.get("path")
        if not isinstance(rel, str) or not safe_path(rel):
            raise ValueError(f"unsafe baseline path: {rel!r}")
        absolute = root / rel
        ensure_contained(root, absolute)
        kind = current_kind(absolute)
        if entry.get("state") == "new":
            action = "noop" if kind == "absent" else "delete"
        else:
            action = "restore"
        actions.append({"path": rel, "baseline": entry.get("state"), "current": kind, "action": action})
    return actions


def snapshot_current(path: Path) -> dict[str, Any]:
    kind = current_kind(path)
    if kind == "file":
        return {"kind": kind, "data": path.read_bytes(), "mode": stat.S_IMODE(path.stat().st_mode)}
    if kind == "symlink":
        return {"kind": kind, "target": os.readlink(path)}
    if kind == "absent":
        return {"kind": kind}
    raise ValueError(f"refusing to replace non-file path: {path}")


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        raise ValueError(f"refusing to delete directory or special path: {path}")


def write_state(path: Path, state: dict[str, Any]) -> None:
    remove_path(path)
    kind = state["kind"]
    if kind == "absent":
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "symlink":
        path.symlink_to(state["target"])
    elif kind == "file":
        path.write_bytes(state["data"])
        path.chmod(state["mode"])


def baseline_state(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    mode = entry.get("mode")
    blob = entry.get("blob")
    if mode not in {"100644", "100755", "120000"} or not isinstance(blob, str):
        raise ValueError(f"invalid baseline entry: {entry}")
    data = git(root, "cat-file", "-p", blob, binary=True)
    assert isinstance(data, bytes)
    if mode == "120000":
        return {"kind": "symlink", "target": data.decode("utf-8")}
    return {"kind": "file", "data": data, "mode": 0o755 if mode == "100755" else 0o644}


def clear_checkboxes(tasks: Path) -> int:
    content = tasks.read_text(encoding="utf-8")
    updated, count = re.subn(r"^- \[[xX]\] (T\d{3})", r"- [ ] \1", content, flags=re.MULTILINE)
    if count:
        atomic_replace(tasks, updated)
    return count


def cmd_rollback(args: argparse.Namespace) -> int:
    try:
        root, feature, plan, tasks = resolve_inputs(args.feature_dir)
        payload = load_baseline(feature, plan)
        actions = actions_for(root, payload)
        if not args.apply:
            emit({"ok": True, "mode": "preview", "baseline": str(baseline_path(feature)), "actions": actions})
            return 0

        current: dict[str, dict[str, Any]] = {}
        desired: dict[str, dict[str, Any]] = {}
        entries = {entry["path"]: entry for entry in payload["entries"]}
        for action in actions:
            rel = action["path"]
            ensure_contained(root, root / rel)
            current[rel] = snapshot_current(root / rel)
            desired[rel] = (
                {"kind": "absent"}
                if entries[rel]["state"] == "new"
                else baseline_state(root, entries[rel])
            )
        changed: list[str] = []
        try:
            for action in actions:
                rel = action["path"]
                changed.append(rel)
                write_state(root / rel, desired[rel])
        except Exception:
            for rel in reversed(changed):
                write_state(root / rel, current[rel])
            raise
        reset = clear_checkboxes(tasks)
        effective = [item["path"] for item in actions if item["action"] != "noop"]
        emit({"ok": True, "mode": "applied", "restored_paths": effective, "checkboxes_reset": reset})
        return 0
    except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="OrderSpec work-order baseline and rollback")
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--feature-dir", required=True)
    capture.add_argument("--replace", action="store_true")
    capture.set_defaults(handler=cmd_capture)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--feature-dir", required=True)
    rollback.add_argument("--apply", action="store_true", help="apply previewed rollback")
    rollback.set_defaults(handler=cmd_rollback)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
