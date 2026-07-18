#!/usr/bin/env python3
"""Validate tooling.json v3 bindings against project contracts and local skills."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REF_RE = re.compile(r"^(GOV|STACK|ARCH|CONV)-\d{3}$")
CONTRACT_FILES = {
    "GOV": "constitution.md",
    "STACK": "stack.md",
    "ARCH": "architecture.md",
    "CONV": "conventions.md",
}
VALID_STATUSES = {"installed", "discovered_only", "pending"}


def load_tooling(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def contract_index(root: Path) -> tuple[set[str], set[str]]:
    known: set[str] = set()
    tombstoned: set[str] = set()
    for prefix, filename in CONTRACT_FILES.items():
        path = root / ".orderspec" / "contracts" / filename
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(rf"^\|\s*({prefix}-\d{{3}})\s*\|(.*)$", line)
            if not match:
                continue
            ref = match.group(1)
            known.add(ref)
            if re.search(r"\[(?:removed|tombstone)\b", match.group(2), flags=re.I):
                tombstoned.add(ref)
    return known, tombstoned


def validate_structure(data: dict, root: Path) -> list[str]:
    errors: list[str] = []
    if data.get("version") != 3:
        errors.append("version must be 3; run tooling_config.py migrate")

    skills = data.get("skills")
    if not isinstance(skills, dict):
        return errors + ["skills must be an object"]
    if skills.get("install_policy") != "ask_user":
        errors.append("skills.install_policy must be 'ask_user'")
    if skills.get("install_location") != ".orderspec/skills/":
        errors.append("skills.install_location must be '.orderspec/skills/'")
    bindings = skills.get("bindings")
    if not isinstance(bindings, list):
        return errors + ["skills.bindings must be an array"]

    known, tombstoned = contract_index(root)
    seen_bindings: set[tuple[str, ...]] = set()
    for index, binding in enumerate(bindings):
        label = f"bindings[{index}]"
        if not isinstance(binding, dict):
            errors.append(f"{label} must be an object")
            continue
        refs = binding.get("contract_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
            errors.append(f"{label}.contract_refs must be a non-empty string array")
            refs = []
        elif len(refs) != len(set(refs)):
            errors.append(f"{label}.contract_refs contains duplicates")
        signature = tuple(sorted(refs))
        if signature and signature in seen_bindings:
            errors.append(f"{label} duplicates another contract_refs binding")
        seen_bindings.add(signature)
        for ref in refs:
            if not REF_RE.fullmatch(ref):
                errors.append(f"{label}.contract_refs contains invalid project contract ID '{ref}'")
            elif ref not in known:
                errors.append(f"{label}.contract_refs references unknown ID '{ref}'")
            elif ref in tombstoned:
                errors.append(f"{label}.contract_refs references tombstoned ID '{ref}'")
        required = binding.get("required_skills")
        if not isinstance(required, list) or not required or not all(isinstance(name, str) and name for name in required):
            errors.append(f"{label}.required_skills must be a non-empty string array")
        commands = binding.get("commands", [])
        if not isinstance(commands, list) or not all(isinstance(command, str) and command.startswith("order.") for command in commands):
            errors.append(f"{label}.commands must be an array of order.* command names")
        status = binding.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{label}.status must be 'installed', 'discovered_only', or 'pending', got '{status}'")

    if not isinstance(data.get("docs_sources"), dict):
        errors.append("docs_sources must be an object")
    return errors


def check_installed_skills(data: dict, skills_dir: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    summary = {"installed_and_verified": [], "installed_but_missing": [], "discovered_only": [], "pending": []}
    existing = {
        entry.name.lower()
        for entry in skills_dir.iterdir()
        if entry.is_dir() and (entry / "SKILL.md").is_file()
    } if skills_dir.is_dir() else set()

    for index, binding in enumerate(data.get("skills", {}).get("bindings", [])):
        if not isinstance(binding, dict):
            continue
        status = binding.get("status")
        refs = binding.get("contract_refs", [])
        required = binding.get("required_skills", [])
        if status == "installed":
            missing = []
            verified = []
            for skill_name in required if isinstance(required, list) else []:
                simple = str(skill_name).split("@")[-1].replace("/", "-").lower()
                if any(simple == name or simple in name or name in simple for name in existing):
                    verified.append(skill_name)
                else:
                    missing.append(skill_name)
            if missing:
                errors.append(f"bindings[{index}] ({', '.join(refs)}): status='installed' but skills {missing} not found in {skills_dir}")
                summary["installed_but_missing"].append({"contract_refs": refs, "missing": missing, "verified": verified})
            else:
                summary["installed_and_verified"].append({"contract_refs": refs, "skills": verified})
        elif status in {"discovered_only", "pending"}:
            summary[status].append({"contract_refs": refs, "skills": required})
    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tooling.json bindings")
    parser.add_argument("-C", "--directory", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    tooling_path = root / ".orderspec" / "config" / "tooling.json"
    skills_dir = root / ".orderspec" / "skills"
    data = load_tooling(tooling_path)
    if data is None:
        result = {"ok": False, "errors": [f"tooling.json not found or invalid: {tooling_path}"]}
        print(json.dumps(result, indent=2) if args.json else result["errors"][0])
        return 1
    errors = validate_structure(data, root)
    install_errors, summary = check_installed_skills(data, skills_dir)
    errors.extend(install_errors)
    bindings = data.get("skills", {}).get("bindings", [])
    result = {
        "ok": not errors,
        "errors": errors,
        "total_bindings": len(bindings) if isinstance(bindings, list) else 0,
        "installed_and_verified": len(summary["installed_and_verified"]),
        "installed_but_missing": len(summary["installed_but_missing"]),
        "discovered_only": len(summary["discovered_only"]),
        "pending": len(summary["pending"]),
        "skills_dir_exists": skills_dir.is_dir(),
        "existing_skills": sorted(entry.name for entry in skills_dir.iterdir() if entry.is_dir()) if skills_dir.is_dir() else [],
        "summary": summary,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        print("FAIL: tooling.json validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print(f"OK: {result['total_bindings']} bindings")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
