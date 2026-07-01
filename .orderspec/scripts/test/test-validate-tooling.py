#!/usr/bin/env python3
"""test-validate-tooling.py — regression for deterministic validate_tooling.py"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
VAL = SCRIPT_DIR.parent / "validate_tooling.py"

if not VAL.exists():
    print(f"FATAL: validate_tooling.py not found at {VAL}", file=sys.stderr)
    sys.exit(2)

WORK = Path(tempfile.mkdtemp(prefix="orderspec-val-tooling-"))
pass_count = 0
fail_count = 0

def ok(name):
    global pass_count
    pass_count += 1
    print(f"PASS: {name}", flush=True)

def bad(name):
    global fail_count
    fail_count += 1
    print(f"FAIL: {name}", flush=True)

def reset_work():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def setup_tooling_json(data):
    write(WORK / ".orderspec" / "config" / "tooling.json", json.dumps(data, indent=2))

def setup_skill_dir(name):
    skill_path = WORK / ".orderspec" / "skills" / name
    skill_path.mkdir(parents=True, exist_ok=True)
    (skill_path / "SKILL.md").write_text("# Skill", encoding="utf-8")

def run_val(*args, input_text=None):
    cmd = [PY, str(VAL)] + list(args)
    proc = subprocess.run(
        cmd,
        cwd=str(WORK),
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr

def run_val_json(*args):
    rc, out, err = run_val(*args)
    try:
        data = json.loads(out)
    except Exception as exc:
        bad(f"invalid JSON output for {' '.join(args)} :: rc={rc} err={err!r} exc={exc} out={out!r}")
        return rc, {}, err
    return rc, data, err

# --- Tests ---

# 1. No tooling.json
reset_work()
rc, data, err = run_val_json("--json")
if rc == 1 and "tooling.json not found or invalid" in data["errors"][0]:
    ok("No tooling.json returns error")
else:
    bad(f"No tooling.json failed :: rc={rc} data={data} err={err!r}")

# 2. Valid empty tooling.json
reset_work()
setup_tooling_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "resolution_order": [".orderspec/skills/"],
        "bindings": []
    },
    "docs_sources": {}
})
rc, data, err = run_val_json("--json")
if rc == 0 and data["ok"] is True and data["total_bindings"] == 0:
    ok("Valid empty tooling.json passes")
else:
    bad(f"Valid empty tooling.json failed :: rc={rc} data={data} err={err!r}")

# 3. Invalid version
reset_work()
setup_tooling_json({
    "version": 1,
    "skills": {"bindings": []}
})
rc, data, err = run_val_json("--json")
if rc == 1 and "version must be 2" in data["errors"]:
    ok("Invalid version caught")
else:
    bad(f"Invalid version failed :: rc={rc} data={data} err={err!r}")

# 4. Binding with status='installed' but no skills dir
reset_work()
setup_tooling_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "bindings": [
            {
                "match": {"stack_id": "STACK-002", "technology": "Express"},
                "required_skills": ["express-setup"],
                "status": "installed"
            }
        ]
    }
})
rc, data, err = run_val_json("--json")
if rc == 1 and "status='installed' but .orderspec/skills/ does not exist" in data["errors"][0]:
    ok("Missing skills dir with installed binding caught")
else:
    bad(f"Missing skills dir failed :: rc={rc} data={data} err={err!r}")

# 5. Binding with status='installed' and skill exists
reset_work()
setup_skill_dir("express-setup")
setup_tooling_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "bindings": [
            {
                "match": {"stack_id": "STACK-002", "technology": "Express"},
                "required_skills": ["express-setup"],
                "status": "installed"
            }
        ]
    }
})
rc, data, err = run_val_json("--json")
if rc == 0 and data["installed_and_verified"] == 1 and data["installed_but_missing"] == 0:
    ok("Installed binding with existing skill passes")
else:
    bad(f"Installed binding with skill failed :: rc={rc} data={data} err={err!r}")

# 6. Binding with status='installed' but skill missing
reset_work()
setup_skill_dir("other-skill")
setup_tooling_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "bindings": [
            {
                "match": {"stack_id": "STACK-002", "technology": "Express"},
                "required_skills": ["express-setup"],
                "status": "installed"
            }
        ]
    }
})
rc, data, err = run_val_json("--json")
if rc == 1 and data["installed_and_verified"] == 0 and data["installed_but_missing"] == 1:
    ok("Installed binding with missing skill caught")
else:
    bad(f"Installed binding missing skill failed :: rc={rc} data={data} err={err!r}")

# 7. Binding with invalid status
reset_work()
setup_tooling_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "bindings": [
            {
                "match": {"stack_id": "STACK-002", "technology": "Express"},
                "required_skills": ["express-setup"],
                "status": "unknown"
            }
        ]
    }
})
rc, data, err = run_val_json("--json")
if rc == 1 and "status must be 'installed', 'discovered_only', or 'pending'" in data["errors"][0]:
    ok("Invalid binding status caught")
else:
    bad(f"Invalid binding status failed :: rc={rc} data={data} err={err!r}")

# 8. Mixed statuses summarized correctly
reset_work()
setup_skill_dir("express-setup")
setup_tooling_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "bindings": [
            {
                "match": {"stack_id": "STACK-002", "technology": "Express"},
                "required_skills": ["express-setup"],
                "status": "installed"
            },
            {
                "match": {"stack_id": "STACK-003", "technology": "Mongoose"},
                "required_skills": ["mongoose-setup"],
                "status": "discovered_only"
            },
            {
                "match": {"stack_id": "STACK-004", "technology": "Redis"},
                "required_skills": ["redis-setup"],
                "status": "pending"
            }
        ]
    }
})
rc, data, err = run_val_json("--json")
if rc == 0 and data["installed_and_verified"] == 1 and data["discovered_only"] == 1 and data["pending"] == 1:
    ok("Mixed statuses summarized correctly")
else:
    bad(f"Mixed statuses failed :: rc={rc} data={data} err={err!r}")

# 9. Invalid JSON format
reset_work()
write(WORK / ".orderspec" / "config" / "tooling.json", "{ invalid json }")
rc, out, err = run_val("--json")
if rc == 1 and "tooling.json not found or invalid" in out:
    ok("Malformed tooling.json caught")
else:
    bad(f"Malformed tooling.json failed :: rc={rc} out={out!r} err={err!r}")

# 10. Missing required fields in binding
reset_work()
setup_tooling_json({
    "version": 2,
    "skills": {
        "install_policy": "ask_user",
        "install_location": ".orderspec/skills/",
        "bindings": [
            {
                "match": {"technology": "Express"}, # missing stack_id
                "required_skills": ["express-setup"],
                "status": "installed"
            }
        ]
    }
})
rc, data, err = run_val_json("--json")
if rc == 1 and "missing stack_id" in data["errors"][0]:
    ok("Missing stack_id caught")
else:
    bad(f"Missing stack_id failed :: rc={rc} data={data} err={err!r}")

# Cleanup
if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
sys.exit(0 if fail_count == 0 else 1)