#!/usr/bin/env python3
"""Deterministic mode and phase router for the unified /order.bootstrap command."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


TOP_LEVEL_PHASES = ["contracts", "constitution", "agents", "tooling", "external_rules", "validation"]
TARGETED_PHASES = ["contracts", "validation"]
VALID_MODES = {"init", "refine", "amend", "targeted-amend"}


def emit(value: dict) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def inspect(args: argparse.Namespace) -> int:
    root = Path(args.directory).resolve()
    script = root / ".orderspec/framework/scripts/bootstrap_contracts.py"
    process = subprocess.run(
        [sys.executable, str(script), "inspect", "--json"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    try:
        contract_state = json.loads(process.stdout)
    except json.JSONDecodeError:
        emit({"ok": False, "error": "bootstrap_contract_inspection_failed", "details": process.stderr or process.stdout})
        return 2
    if process.returncode != 0:
        emit({"ok": False, "error": "bootstrap_contract_inspection_failed", "contract_state": contract_state})
        return process.returncode

    targeted_fields = [args.targeted_caller, args.target_contract, args.target_change]
    if any(targeted_fields) and not all(targeted_fields):
        emit({"ok": False, "error": "targeted_amend_requires_caller_contract_and_change"})
        return 64
    if all(targeted_fields):
        mode = "targeted-amend"
    elif contract_state.get("mode") == "init":
        mode = "init"
    elif args.arguments.strip():
        mode = "amend"
    else:
        mode = "refine"
    phases = TARGETED_PHASES if mode == "targeted-amend" else TOP_LEVEL_PHASES
    emit({
        "ok": True,
        "mode": mode,
        "phases": phases,
        "next_phase": phases[0],
        "contract_state": contract_state,
        "scope": {
            "refine_compares": ["framework rules", "project contracts", "bounded project state", "project tooling"],
            "refine_excludes": ["feature artifacts", "code-to-spec drift"],
        },
    })
    return 0


def next_phase(args: argparse.Namespace) -> int:
    if args.mode not in VALID_MODES:
        emit({"ok": False, "error": f"unknown mode: {args.mode}"})
        return 64
    phases = TARGETED_PHASES if args.mode == "targeted-amend" else TOP_LEVEL_PHASES
    completed = args.completed or []
    if len(completed) != len(set(completed)):
        emit({"ok": False, "error": "completed phases contain duplicates"})
        return 64
    unknown = sorted(set(completed) - set(phases))
    if unknown:
        emit({"ok": False, "error": "completed phases contain unknown values", "unknown": unknown})
        return 64
    expected_prefix = phases[:len(completed)]
    if completed != expected_prefix:
        emit({"ok": False, "error": "phases must complete in declared order", "expected_prefix": expected_prefix})
        return 64
    if len(completed) == len(phases):
        emit({"ok": True, "mode": args.mode, "status": "ready_to_finalize", "next_phase": None})
    else:
        emit({"ok": True, "mode": args.mode, "status": "in_progress", "next_phase": phases[len(completed)]})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Route unified bootstrap phases")
    parser.add_argument("-C", "--directory", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--arguments", default="")
    inspect_parser.add_argument("--targeted-caller")
    inspect_parser.add_argument("--target-contract", choices=["constitution", "stack", "architecture", "conventions"])
    inspect_parser.add_argument("--target-change")
    inspect_parser.set_defaults(func=inspect)
    next_parser = sub.add_parser("next")
    next_parser.add_argument("--mode", required=True)
    next_parser.add_argument("--completed", action="append")
    next_parser.set_defaults(func=next_phase)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
