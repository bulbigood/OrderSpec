#!/usr/bin/env python3
"""tooling_config.py — deterministic manager for .orderspec/config/tooling.json"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


TOOLING_PATH = Path(".orderspec/config/tooling.json")


def load_tooling() -> dict:
    if not TOOLING_PATH.exists():
        return {"version": 2, "skills": {"bindings": []}, "docs_sources": {}}
    return json.loads(TOOLING_PATH.read_text(encoding="utf-8"))


def save_tooling(data: dict) -> None:
    TOOLING_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOOLING_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_binding(args: argparse.Namespace) -> int:
    data = load_tooling()
    bindings = data.setdefault("skills", {}).setdefault("bindings", [])
    
    req_skills = args.skills.split(",") if "," in args.skills else [args.skills]
    req_skills = [s.strip() for s in req_skills if s.strip()]
    
    # Check if binding for this stack_id already exists
    for b in bindings:
        if b.get("match", {}).get("stack_id") == args.stack_id:
            # Update existing
            b["required_skills"] = req_skills
            b["status"] = args.status
            save_tooling(data)
            print(json.dumps({"ok": True, "action": "updated", "stack_id": args.stack_id}))
            return 0
            
    # Add new
    bindings.append({
        "match": {
            "stack_id": args.stack_id,
            "technology": args.technology
        },
        "required_skills": req_skills,
        "status": args.status
    })
    save_tooling(data)
    print(json.dumps({"ok": True, "action": "created", "stack_id": args.stack_id}))
    return 0


def set_docs_policy(args: argparse.Namespace) -> int:
    data = load_tooling()
    docs = data.setdefault("docs_sources", {})
    
    source = docs.setdefault(args.source, {})
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
    
    p_add = sub.add_parser("add-binding")
    p_add.add_argument("--stack-id", required=True)
    p_add.add_argument("--technology", required=True)
    p_add.add_argument("--skills", required=True, help="Comma-separated skill names")
    p_add.add_argument("--status", choices=["installed", "discovered_only", "pending"], default="installed")
    p_add.set_defaults(func=add_binding)
    
    p_docs = sub.add_parser("set-docs-policy")
    p_docs.add_argument("--source", required=True)
    p_docs.add_argument("--policy", required=True, choices=["required_if_available", "disabled", "optional"])
    p_docs.add_argument("--commands", help="Comma-separated command names")
    p_docs.add_argument("--fallback")
    p_docs.set_defaults(func=set_docs_policy)
    
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
