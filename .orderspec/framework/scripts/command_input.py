#!/usr/bin/env python3
"""Parse OrderSpec command controls separately from semantic user text."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from typing import Any


FLAG = "flag"
VALUE = "value"

COMMAND_CONTROLS: dict[str, dict[str, str]] = {
    "order.bootstrap": {},
    "order.feature": {"--select": VALUE},
    "order.spec": {"--new": FLAG, "--split": FLAG},
    "order.code-to-spec": {"--new": FLAG},
    "order.spec-check": {},
    "order.plan": {"--force": FLAG},
    "order.plan-check": {},
    "order.tasks": {"--force": FLAG, "--force-upstream": FLAG},
    "order.tasks-check": {},
    "order.code": {
        "--reset": FLAG,
        "--phase": FLAG,
        "--delegated": FLAG,
        "--all": FLAG,
        "--local": FLAG,
        "--no-subagents": FLAG,
        "--force": FLAG,
        "--resume": FLAG,
    },
    "order.code-check": {"--base": VALUE},
}


def control_name(flag: str) -> str:
    return flag[2:].replace("-", "_")


def validate_combinations(command: str, controls: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if command == "order.spec" and controls.get("new") and controls.get("split"):
        errors.append("--new and --split are mutually exclusive")
    if command == "order.code":
        selected_modes = [
            name for name in ("phase", "delegated", "all", "local", "no_subagents")
            if controls.get(name)
        ]
        if len(selected_modes) > 1:
            errors.append("implementation mode controls are mutually exclusive")
        if controls.get("reset") and len(controls) > 1:
            errors.append("--reset cannot be combined with other controls")
    return errors


def parse_input(command: str, arguments: str) -> dict[str, Any]:
    try:
        tokens = shlex.split(arguments)
    except ValueError as exc:
        return {
            "ok": False,
            "command": command,
            "controls": {},
            "semantic_input": "",
            "semantic_tokens": [],
            "validation_errors": [f"invalid arguments: {exc}"],
        }

    allowed = COMMAND_CONTROLS.get(command, {})
    controls: dict[str, Any] = {}
    semantic_tokens: list[str] = []
    errors: list[str] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            semantic_tokens.append(token)
            index += 1
            continue

        kind = allowed.get(token)
        if kind is None:
            errors.append(f"unsupported control: {token}")
            index += 1
            continue

        name = control_name(token)
        if name in controls:
            errors.append(f"control may appear only once: {token}")
            index += 1
            continue

        if kind == FLAG:
            controls[name] = True
            index += 1
            continue

        if index + 1 >= len(tokens) or tokens[index + 1].startswith("--"):
            errors.append(f"{token} requires one value")
            index += 1
            continue

        controls[name] = tokens[index + 1]
        index += 2

    errors.extend(validate_combinations(command, controls))
    return {
        "ok": not errors,
        "command": command,
        "controls": controls,
        "semantic_input": " ".join(semantic_tokens),
        "semantic_tokens": semantic_tokens,
        "validation_errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    parser.add_argument("--arguments", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = parse_input(args.command, args.arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
