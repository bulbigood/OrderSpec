#!/usr/bin/env python3
"""Resolve a gate target and command arguments without mutating active state."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from active_feature import find_feature, load_state, posix, safe_rel  # noqa: E402
from common import SPECS_ROOT  # noqa: E402


COMMANDS = {"order.spec-check", "order.plan-check", "order.tasks-check", "order.code-check"}


def emit(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def emit_shell(data: dict) -> None:
    mapping = {
        "FEATURE_DIR": data.get("feature_directory_abs", ""),
        "FEATURE_DIR_REL": data.get("feature_directory", ""),
        "FEATURE_ID": data.get("feature_id") or "",
        "BASE_REF": data.get("base_ref") or "",
        "EXPLICIT_TARGET": "true" if data.get("explicit") else "false",
    }
    for key, value in mapping.items():
        print(f"{key}={shlex.quote(str(value))}")


def fail(code: str, message: str, **extra) -> int:
    emit({"ok": False, "error": code, "message": message, **extra})
    return 1


def parse_input(command: str, arguments: str) -> tuple[str | None, str | None, list[str]]:
    try:
        tokens = shlex.split(arguments)
    except ValueError as exc:
        return None, None, [f"invalid arguments: {exc}"]

    if command == "order.plan-check":
        return None, None, [] if not tokens else ["order.plan-check accepts no arguments"]

    feature_ref = None
    base_ref = None
    errors: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if command == "order.code-check" and token == "--base":
            if index + 1 >= len(tokens):
                errors.append("--base requires one ref")
                break
            if base_ref is not None:
                errors.append("--base may appear only once")
                break
            base_ref = tokens[index + 1]
            index += 2
            continue
        if token.startswith("-"):
            errors.append(f"unsupported argument: {token}")
            break
        if feature_ref is not None:
            errors.append("at most one feature reference is allowed")
            break
        feature_ref = token
        index += 1
    return feature_ref, base_ref, errors


def resolve(root: Path, command: str, arguments: str, specs_root: str) -> tuple[dict, int]:
    feature_ref, base_ref, errors = parse_input(command, arguments)
    if errors:
        return {"ok": False, "error": "unsupported_arguments", "validation_errors": errors}, 1

    if not safe_rel(specs_root):
        return {"ok": False, "error": "invalid_specs_root"}, 1

    explicit = feature_ref is not None
    if explicit:
        state, matches = find_feature(root, Path(specs_root), feature_ref)
        if state is None:
            error = "ambiguous_feature" if len(matches) > 1 else "feature_not_found"
            return {"ok": False, "error": error, "feature_ref": feature_ref, "matches": matches}, 1
    else:
        state, state_errors, _ = load_state(root)
        if state_errors:
            return {"ok": False, "error": "invalid_active_feature", "validation_errors": state_errors}, 1
        if not state.get("active"):
            return {"ok": False, "error": "no_active_feature"}, 1

    feature_dir_rel = state.get("feature_directory")
    if not isinstance(feature_dir_rel, str) or not safe_rel(feature_dir_rel):
        return {"ok": False, "error": "unsafe_feature_directory"}, 1
    feature_dir = (root / feature_dir_rel).resolve()
    try:
        feature_dir.relative_to(root)
    except ValueError:
        return {"ok": False, "error": "unsafe_feature_directory"}, 1
    if not feature_dir.is_dir():
        return {"ok": False, "error": "feature_directory_missing", "feature_directory": feature_dir_rel}, 1

    return {
        "ok": True,
        "command": command,
        "explicit": explicit,
        "feature_ref": feature_ref,
        "feature_id": state.get("feature_id"),
        "feature_directory": posix(Path(feature_dir_rel)),
        "feature_directory_abs": str(feature_dir),
        "base_ref": base_ref,
        "state_written": False,
    }, 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True, choices=sorted(COMMANDS))
    parser.add_argument("--arguments", default="")
    parser.add_argument("--specs-root", default=posix(SPECS_ROOT))
    parser.add_argument("-C", "--cwd", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--shell-vars", action="store_true")
    args = parser.parse_args()
    result, rc = resolve(Path(args.cwd).resolve(), args.command, args.arguments, args.specs_root)
    if args.shell_vars and rc == 0:
        emit_shell(result)
    else:
        emit(result)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
