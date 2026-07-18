#!/usr/bin/env python3
"""Deterministic manager and v2-to-v3 migrator for tooling.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOLING_PATH = Path(".orderspec/config/tooling.json")


def defaults() -> dict:
    return {
        "version": 3,
        "skills": {
            "install_policy": "ask_user",
            "install_location": ".orderspec/skills/",
            "resolution_order": [".orderspec/skills/"],
            "bindings": [],
        },
        "docs_sources": {},
    }


def load_tooling() -> dict:
    if not TOOLING_PATH.exists():
        return defaults()
    value = json.loads(TOOLING_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("tooling.json root must be an object")
    return value


def save_tooling(data: dict) -> None:
    TOOLING_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOOLING_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def migrate(args: argparse.Namespace) -> int:
    data = load_tooling()
    version = data.get("version")
    if version == 3:
        print(json.dumps({"ok": True, "action": "unchanged", "version": 3}))
        return 0
    if version != 2:
        print(json.dumps({"ok": False, "error": f"unsupported tooling version: {version}"}))
        return 1
    migrated = []
    errors = []
    for binding in data.get("skills", {}).get("bindings", []):
        match = binding.pop("match", {}) if isinstance(binding, dict) else {}
        stack_id = match.get("stack_id") if isinstance(match, dict) else None
        if stack_id:
            binding["contract_refs"] = [stack_id]
            migrated.append(stack_id)
        else:
            errors.append("v2 binding missing match.stack_id")
    if errors:
        print(json.dumps({"ok": False, "error": "tooling migration blocked", "details": errors}))
        return 1
    data["version"] = 3
    save_tooling(data)
    print(json.dumps({"ok": True, "action": "migrated", "from": 2, "to": 3, "contract_refs": migrated}))
    return 0


def add_binding(args: argparse.Namespace) -> int:
    data = load_tooling()
    if data.get("version") != 3:
        print(json.dumps({"ok": False, "error": "run tooling_config.py migrate first"}))
        return 1
    refs = list(dict.fromkeys(args.contract_ref))
    required = [value.strip() for value in args.skills.split(",") if value.strip()]
    bindings = data.setdefault("skills", {}).setdefault("bindings", [])
    for binding in bindings:
        if sorted(binding.get("contract_refs", [])) == sorted(refs):
            binding.update({"required_skills": required, "commands": args.commands or [], "status": args.status})
            action = "updated"
            break
    else:
        bindings.append({"contract_refs": refs, "required_skills": required, "commands": args.commands or [], "status": args.status})
        action = "created"
    save_tooling(data)
    print(json.dumps({"ok": True, "action": action, "contract_refs": refs}))
    return 0


def set_docs_policy(args: argparse.Namespace) -> int:
    data = load_tooling()
    if data.get("version") != 3:
        print(json.dumps({"ok": False, "error": "run tooling_config.py migrate first"}))
        return 1
    source = data.setdefault("docs_sources", {}).setdefault(args.source, {})
    source["policy"] = args.policy
    if args.commands:
        source["commands"] = args.commands.split(",")
    if args.fallback:
        source["fallback_when_unavailable"] = args.fallback
    save_tooling(data)
    print(json.dumps({"ok": True, "source": args.source, "policy": args.policy}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage tooling.json")
    sub = parser.add_subparsers(dest="command", required=True)
    migration = sub.add_parser("migrate")
    migration.set_defaults(func=migrate)
    binding = sub.add_parser("add-binding")
    binding.add_argument("--contract-ref", action="append", required=True)
    binding.add_argument("--skills", required=True)
    binding.add_argument("--commands", action="append")
    binding.add_argument("--status", choices=["installed", "discovered_only", "pending"], default="installed")
    binding.set_defaults(func=add_binding)
    docs = sub.add_parser("set-docs-policy")
    docs.add_argument("--source", required=True)
    docs.add_argument("--policy", required=True, choices=["required_if_available", "disabled", "optional"])
    docs.add_argument("--commands")
    docs.add_argument("--fallback")
    docs.set_defaults(func=set_docs_policy)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
