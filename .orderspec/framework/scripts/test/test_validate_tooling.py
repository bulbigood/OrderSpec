#!/usr/bin/env python3
"""Regression tests for tooling v3 generic project-contract references."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
VALIDATOR = SCRIPT_DIR.parent / "validate_tooling.py"
MANAGER = SCRIPT_DIR.parent / "tooling_config.py"
WORK = Path(tempfile.mkdtemp(prefix="orderspec-val-tooling-"))
passed = failed = 0


def ok(name):
    global passed
    passed += 1
    print(f"PASS: {name}")


def bad(name, detail=""):
    global failed
    failed += 1
    print(f"FAIL: {name} :: {detail}")


def reset():
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    contracts = WORK / ".orderspec/contracts"
    contracts.mkdir(parents=True)
    (contracts / "constitution.md").write_text("| GOV-001 | Project MUST be safe | | |\n", encoding="utf-8")
    (contracts / "stack.md").write_text("| STACK-001 | Python | 3.12 | Runtime | |\n", encoding="utf-8")
    (contracts / "architecture.md").write_text("| ARCH-001 | Modules MUST be isolated |\n", encoding="utf-8")
    (contracts / "conventions.md").write_text(
        "| CONV-001 | Typed APIs | Public APIs MUST be typed | |\n"
        "| CONV-002 | [removed — obsolete] | | |\n",
        encoding="utf-8",
    )


def write_json(data):
    path = WORK / ".orderspec/config/tooling.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def config(bindings=None, version=3):
    return {
        "version": version,
        "skills": {
            "install_policy": "ask_user",
            "install_location": ".orderspec/skills/",
            "resolution_order": [".orderspec/skills/"],
            "bindings": bindings or [],
        },
        "docs_sources": {},
    }


def binding(refs, status="installed", skills=None):
    return {
        "contract_refs": refs,
        "required_skills": skills or ["project-method"],
        "commands": ["order.plan"],
        "status": status,
    }


def skill(name="project-method"):
    path = WORK / ".orderspec/skills" / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text("# Skill\n", encoding="utf-8")


def run(script, *args):
    process = subprocess.run([PY, str(script), *args], cwd=WORK, text=True, capture_output=True)
    try:
        data = json.loads(process.stdout)
    except json.JSONDecodeError:
        data = {"raw": process.stdout, "stderr": process.stderr}
    return process.returncode, data


reset()
rc, data = run(VALIDATOR, "--json")
ok("missing tooling fails") if rc == 1 else bad("missing tooling fails", data)

reset()
write_json(config())
rc, data = run(VALIDATOR, "--json")
ok("empty v3 config passes") if rc == 0 else bad("empty v3 config passes", data)

for ref in ["GOV-001", "STACK-001", "ARCH-001", "CONV-001"]:
    reset(); skill(); write_json(config([binding([ref])]))
    rc, data = run(VALIDATOR, "--json")
    ok(f"generic binding accepts {ref}") if rc == 0 else bad(f"generic binding accepts {ref}", data)

reset(); skill(); write_json(config([binding(["ARCH-999"])]))
rc, data = run(VALIDATOR, "--json")
ok("unknown contract ref rejected") if rc == 1 and "unknown ID" in " ".join(data["errors"]) else bad("unknown contract ref rejected", data)

reset(); skill(); write_json(config([binding(["CONV-002"])]))
rc, data = run(VALIDATOR, "--json")
ok("tombstoned contract ref rejected") if rc == 1 and "tombstoned ID" in " ".join(data["errors"]) else bad("tombstoned contract ref rejected", data)

reset(); write_json(config([binding(["STACK-001"])]))
rc, data = run(VALIDATOR, "--json")
ok("missing installed skill rejected") if rc == 1 and data["installed_but_missing"] == 1 else bad("missing installed skill rejected", data)

reset(); write_json(config([binding(["STACK-001"], status="discovered_only")]))
rc, data = run(VALIDATOR, "--json")
ok("discovered-only binding valid") if rc == 0 and data["discovered_only"] == 1 else bad("discovered-only binding valid", data)

reset()
write_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "bindings": [{"match": {"stack_id": "STACK-001", "technology": "Python"}, "required_skills": ["python"], "status": "pending"}],
    },
    "docs_sources": {},
})
rc, data = run(MANAGER, "migrate")
migrated = json.loads((WORK / ".orderspec/config/tooling.json").read_text(encoding="utf-8"))
ok("v2 migrates to contract_refs") if rc == 0 and migrated["version"] == 3 and migrated["skills"]["bindings"][0]["contract_refs"] == ["STACK-001"] else bad("v2 migrates to contract_refs", data)

reset(); write_json(config())
rc, data = run(MANAGER, "add-binding", "--contract-ref", "ARCH-001", "--contract-ref", "CONV-001", "--skills", "architecture-method", "--commands", "order.plan", "--status", "pending")
managed = json.loads((WORK / ".orderspec/config/tooling.json").read_text(encoding="utf-8"))
ok("manager writes multi-ref binding") if rc == 0 and managed["skills"]["bindings"][0]["contract_refs"] == ["ARCH-001", "CONV-001"] else bad("manager writes multi-ref binding", data)

shutil.rmtree(WORK, ignore_errors=True)
print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
