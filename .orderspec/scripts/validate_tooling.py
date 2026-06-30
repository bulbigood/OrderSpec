#!/usr/bin/env python3
"""validate_tooling.py — verify tooling.json bindings match installed skills.

Checks that every binding with status="installed" has corresponding files
in .orderspec/skills/. Also validates tooling.json structure.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def load_tooling(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def validate_structure(data: dict) -> list[str]:
    errors = []
    
    if data.get("version") != 2:
        errors.append("version must be 2")
    
    skills = data.get("skills", {})
    if not isinstance(skills, dict):
        errors.append("skills must be an object")
        return errors
    
    if skills.get("install_policy") != "ask_user":
        errors.append("skills.install_policy must be 'ask_user'")
    
    install_loc = skills.get("install_location")
    if install_loc != ".orderspec/skills/":
        errors.append(f"skills.install_location must be '.orderspec/skills/', got '{install_loc}'")
    
    bindings = skills.get("bindings", [])
    if not isinstance(bindings, list):
        errors.append("skills.bindings must be an array")
        return errors
    
    for i, b in enumerate(bindings):
        if not isinstance(b, dict):
            errors.append(f"bindings[{i}] must be an object")
            continue
        
        match = b.get("match", {})
        if not isinstance(match, dict):
            errors.append(f"bindings[{i}].match must be an object")
            continue
        
        if "stack_id" not in match:
            errors.append(f"bindings[{i}].match missing stack_id")
        
        if "technology" not in match:
            errors.append(f"bindings[{i}].match missing technology")
        
        req = b.get("required_skills")
        if not isinstance(req, list) or not req:
            errors.append(f"bindings[{i}].required_skills must be a non-empty array")
        
        status = b.get("status")
        if status not in ("installed", "discovered_only", "pending"):
            errors.append(f"bindings[{i}].status must be 'installed', 'discovered_only', or 'pending', got '{status}'")
    
    docs = data.get("docs_sources", {})
    if not isinstance(docs, dict):
        errors.append("docs_sources must be an object")
    
    return errors


def check_installed_skills(data: dict, skills_dir: Path) -> tuple[list[str], dict]:
    """Verify that 'installed' bindings have actual files.
    
    Returns (errors, summary) where summary contains:
    - installed_and_verified: bindings where files exist
    - installed_but_missing: bindings where files don't exist
    - discovered_only: bindings with discovered_only status
    - pending: bindings with pending status
    """
    errors = []
    bindings = data.get("skills", {}).get("bindings", [])
    summary = {
        "installed_and_verified": [],
        "installed_but_missing": [],
        "discovered_only": [],
        "pending": [],
    }
    
    if not skills_dir.exists():
        for i, b in enumerate(bindings):
            if b.get("status") == "installed":
                req = b.get("required_skills", [])
                tech = b.get("match", {}).get("technology", "?")
                errors.append(
                    f"bindings[{i}] ({tech}): status='installed' but .orderspec/skills/ does not exist; "
                    f"expected skills: {req}"
                )
                summary["installed_but_missing"].append({
                    "technology": tech,
                    "skills": req,
                })
            elif b.get("status") == "discovered_only":
                summary["discovered_only"].append(b.get("match", {}).get("technology", "?"))
            elif b.get("status") == "pending":
                summary["pending"].append(b.get("match", {}).get("technology", "?"))
        return errors, summary
    
    existing_skills = set()
    for entry in skills_dir.iterdir():
        if entry.is_dir():
            existing_skills.add(entry.name.lower())
    
    for i, b in enumerate(bindings):
        status = b.get("status")
        tech = b.get("match", {}).get("technology", "?")
        req_skills = b.get("required_skills", [])
        
        if status == "installed":
            missing_skills = []
            verified_skills = []
            
            for skill_name in req_skills:
                simple_name = skill_name.split("@")[-1] if "@" in skill_name else skill_name
                simple_name = simple_name.replace("/", "-").lower()
                
                found = any(
                    simple_name in existing or existing in simple_name
                    for existing in existing_skills
                )
                
                if found:
                    verified_skills.append(skill_name)
                else:
                    missing_skills.append(skill_name)
            
            if missing_skills:
                errors.append(
                    f"bindings[{i}] ({tech}): status='installed' but skills {missing_skills} "
                    f"not found in {skills_dir} (existing: {sorted(existing_skills)})"
                )
                summary["installed_but_missing"].append({
                    "technology": tech,
                    "missing": missing_skills,
                    "verified": verified_skills,
                })
            else:
                summary["installed_and_verified"].append({
                    "technology": tech,
                    "skills": verified_skills,
                })
        elif status == "discovered_only":
            summary["discovered_only"].append(tech)
        elif status == "pending":
            summary["pending"].append(tech)
    
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
        result = {
            "ok": False,
            "errors": [f"tooling.json not found or invalid: {tooling_path}"],
            "installed_count": 0,
            "discovered_count": 0,
            "pending_count": 0,
        }
        print(json.dumps(result, indent=2) if args.json else "FAIL: tooling.json not found")
        return 1
    
    struct_errors = validate_structure(data)
    install_errors, summary = check_installed_skills(data, skills_dir)
    all_errors = struct_errors + install_errors
    
    bindings = data.get("skills", {}).get("bindings", [])
    
    result = {
        "ok": len(all_errors) == 0,
        "errors": all_errors,
        "total_bindings": len(bindings),
        "installed_and_verified": len(summary["installed_and_verified"]),
        "installed_but_missing": len(summary["installed_but_missing"]),
        "discovered_only": len(summary["discovered_only"]),
        "pending": len(summary["pending"]),
        "skills_dir_exists": skills_dir.exists(),
        "existing_skills": sorted([e.name for e in skills_dir.iterdir() if e.is_dir()]) if skills_dir.exists() else [],
        "summary": summary,
    }
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if all_errors:
            print("FAIL: tooling.json validation errors:")
            for e in all_errors:
                print(f"  - {e}")
            print()
            print(f"Skills directory: {skills_dir}")
            print(f"Existing skills: {result['existing_skills']}")
        else:
            print(f"OK: {len(bindings)} bindings")
            print(f"  Installed & verified: {result['installed_and_verified']}")
            print(f"  Discovered only: {result['discovered_only']}")
            print(f"  Pending: {result['pending']}")
            print(f"  Skills directory: {skills_dir}")
            print(f"  Existing skills: {result['existing_skills']}")
    
    return 0 if not all_errors else 1


if __name__ == "__main__":
    sys.exit(main())
