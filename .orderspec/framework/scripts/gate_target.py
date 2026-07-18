#!/usr/bin/env python3
"""Resolve a gate target and command arguments without mutating active state."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from active_feature import load_state, posix, safe_rel, validate_state_references  # noqa: E402
from command_input import parse_input  # noqa: E402
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


def resolve(
    root: Path,
    command: str,
    arguments: str,
    specs_root: str,
    parsed_input: dict | None = None,
) -> tuple[dict, int]:
    parsed = parsed_input or parse_input(command, arguments)
    if not parsed.get("ok"):
        return {
            "ok": False,
            "error": "unsupported_arguments",
            "validation_errors": parsed.get("validation_errors", []),
        }, 1

    if not safe_rel(specs_root):
        return {"ok": False, "error": "invalid_specs_root"}, 1

    state, state_errors, state_exists = load_state(root)
    if state_errors:
        return {"ok": False, "error": "invalid_active_feature", "validation_errors": state_errors}, 1
    if not state_exists:
        return {"ok": False, "error": "active_feature_state_missing"}, 1
    if not state.get("active"):
        return {"ok": False, "error": "no_active_feature"}, 1
    reference_errors = validate_state_references(root, state)
    if reference_errors:
        return {
            "ok": False,
            "error": "invalid_active_feature",
            "validation_errors": reference_errors,
        }, 1

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
        "explicit": False,
        "feature_ref": None,
        "feature_id": state.get("feature_id"),
        "feature_directory": posix(Path(feature_dir_rel)),
        "feature_directory_abs": str(feature_dir),
        "base_ref": parsed.get("controls", {}).get("base"),
        "semantic_input": parsed.get("semantic_input", ""),
        "input": parsed,
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
