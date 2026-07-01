#!/usr/bin/env python3
"""test-setup.py — regression tests for setup.py path resolution and phase setup.

Portable: Python 3 standard library only.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
SETUP = SCRIPT_DIR.parent / "setup.py"

if not SETUP.exists():
    print(f"FATAL: setup.py not found at {SETUP}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────

LOG_TO_FILE = False  # Set to True to also write test results to test/test-setup.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-setup.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-setup-test-"))

pass_count = 0
fail_count = 0


def ok(name):
    global pass_count
    pass_count += 1
    msg = f"PASS: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def bad(name):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def reset_repo():
    """Create a clean fake OrderSpec repo."""
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / ".orderspec" / "scripts").mkdir(parents=True, exist_ok=True)
    (WORK / ".orderspec" / "framework" / "templates").mkdir(parents=True, exist_ok=True)
    (WORK / ".orderspec" / "config" / "templates" / "overrides").mkdir(parents=True, exist_ok=True)
    (WORK / ".orderspec" / "state").mkdir(parents=True, exist_ok=True)

    # Root marker for common.py find_orderspec_root().
    # Scripts are not copied; setup.py is executed from its real location with
    # ORDERSPEC_ROOT pointing here.
    write_core_template("plan-template", "CORE PLAN TEMPLATE\n")
    write_core_template("tasks-template", "CORE TASKS TEMPLATE\n")


def write_core_template(name, content):
    path = WORK / ".orderspec" / "framework" / "templates" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_override_template(name, content):
    path = WORK / ".orderspec" / "config" / "templates" / "overrides" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def set_active_feature_state(feature_dir):
    state_file = WORK / ".orderspec" / "state" / "active-feature.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({
            "feature_directory": feature_dir,
            "spec_file": str(Path(feature_dir) / "spec.md"),
            "status": "draft",
        }) + "\n",
        encoding="utf-8",
    )


def make_feature(feature_dir="specs/F", spec=True, plan=False, tasks=False):
    fdir = WORK / feature_dir
    fdir.mkdir(parents=True, exist_ok=True)

    if spec:
        (fdir / "spec.md").write_text("# Spec\n- **REQ-001**: System MUST work\n", encoding="utf-8")

    if plan:
        (fdir / "plan.md").write_text("EXISTING PLAN\n", encoding="utf-8")

    if tasks:
        (fdir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")

    set_active_feature_state(feature_dir)
    return fdir


def run_setup(*args, env=None):
    cmd = [PY, str(SETUP)] + list(args)
    e = os.environ.copy()
    e["ORDERSPEC_ROOT"] = str(WORK)
    e.pop("SPECIFY_FEATURE_DIRECTORY", None)
    e.pop("SPECIFY_FEATURE", None)
    if env:
        e.update(env)

    proc = subprocess.run(
        cmd,
        cwd=str(WORK),
        capture_output=True,
        text=True,
        env=e,
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_json_stdout(stdout):
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout is not JSON: {stdout!r}") from exc


def assert_true(cond, name, detail=""):
    if cond:
        ok(name)
    else:
        bad(f"{name}{' :: ' + detail if detail else ''}")


def assert_rc(expected, actual, name, out="", err=""):
    if actual == expected:
        ok(name)
    else:
        bad(f"{name} (rc={actual} want {expected}) :: stdout={out!r} stderr={err!r}")


# ── Tests ────────────────────────────────────────────────────────────────────

# 1. paths --json resolves from SPECIFY_FEATURE_DIRECTORY and is read-only
reset_repo()
env = {"SPECIFY_FEATURE_DIRECTORY": "specs/F"}
rc, out, err = run_setup("paths", "--json", env=env)
assert_rc(0, rc, "paths --json resolves explicit feature dir", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"].endswith("specs/F"), "paths returns FEATURE_DIR")
assert_true(data["FEATURE_SPEC"].endswith("specs/F/spec.md"), "paths returns FEATURE_SPEC")
assert_true(data["IMPL_PLAN"].endswith("specs/F/plan.md"), "paths returns IMPL_PLAN")
assert_true(data["REPO_ROOT"] == str(WORK.resolve()), "paths returns REPO_ROOT")
assert_true(not (WORK / "specs" / "F").exists(), "paths is read-only and does not create feature dir")
assert_true(
    not (WORK / ".orderspec" / "state" / "active-feature.json").exists(),
    "paths is read-only and does not write active-feature state",
)

# 2. plan --json blocks when spec.md is missing
reset_repo()
set_active_feature_state("specs/F")
rc, out, err = run_setup("plan", "--json")
assert_rc(2, rc, "plan blocks without spec.md", out, err)
assert_true(not (WORK / "specs" / "F" / "plan.md").exists(), "plan block does not create plan.md")

# 3. plan --json creates plan.md from core template when spec.md exists
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=False)
rc, out, err = run_setup("plan", "--json")
assert_rc(0, rc, "plan creates plan.md when spec.md exists", out, err)
data = parse_json_stdout(out)
assert_true((fdir / "plan.md").read_text(encoding="utf-8") == "CORE PLAN TEMPLATE\n", "plan.md copied from core template")
assert_true(data["FEATURE_DIR"] == str(fdir.resolve()), "plan JSON includes canonical FEATURE_DIR")
assert_true(data["SPECS_DIR"] == str(fdir.resolve()), "plan JSON includes deprecated SPECS_DIR alias")
assert_true(data["REPO_ROOT"] == str(WORK.resolve()), "plan JSON includes REPO_ROOT")

# 4. plan --json does not overwrite existing plan without --refresh-template
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True)
rc, out, err = run_setup("plan", "--json")
assert_rc(0, rc, "plan preserves existing plan without refresh", out, err)
assert_true((fdir / "plan.md").read_text(encoding="utf-8") == "EXISTING PLAN\n", "existing plan content preserved")

# 5. plan --json --refresh-template overwrites existing plan
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True)
rc, out, err = run_setup("plan", "--json", "--refresh-template")
assert_rc(0, rc, "plan refresh exits zero", out, err)
assert_true((fdir / "plan.md").read_text(encoding="utf-8") == "CORE PLAN TEMPLATE\n", "refresh replaces existing plan with template")
data = parse_json_stdout(out)
assert_true(data["PLAN_REFRESHED"] is True, "plan JSON marks PLAN_REFRESHED=true")

# 6. override template wins over core template
reset_repo()
write_override_template("plan-template", "OVERRIDE PLAN TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=False)
rc, out, err = run_setup("plan", "--json")
assert_rc(0, rc, "plan with override exits zero", out, err)
assert_true((fdir / "plan.md").read_text(encoding="utf-8") == "OVERRIDE PLAN TEMPLATE\n", "override plan-template wins")

# 7. relative SPECIFY_FEATURE_DIRECTORY is resolved under repo root and persisted
reset_repo()
env = {"SPECIFY_FEATURE_DIRECTORY": "features/custom-F"}
fdir = WORK / "features" / "custom-F"
fdir.mkdir(parents=True, exist_ok=True)
(fdir / "spec.md").write_text("# Spec\n- **REQ-001**: System MUST work\n", encoding="utf-8")
rc, out, err = run_setup("plan", "--json", env=env)
assert_rc(0, rc, "relative SPECIFY_FEATURE_DIRECTORY works", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"] == str(fdir.resolve()), "relative feature dir resolved under repo root")
state = json.loads((WORK / ".orderspec" / "state" / "active-feature.json").read_text(encoding="utf-8"))
assert_true(
    state["feature_directory"] == "features/custom-F",
    "relative feature dir persisted to active-feature state",
)

# 8. active-feature state fallback works when env var is absent
reset_repo()
fdir = make_feature("features/custom-F", spec=True, plan=False)
rc, out, err = run_setup("paths", "--json")
assert_rc(0, rc, "paths falls back to active-feature state", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"] == str(fdir.resolve()), "active-feature state fallback resolves FEATURE_DIR")

# 9. tasks --json blocks without plan.md
reset_repo()
make_feature("specs/F", spec=True, plan=False)
rc, out, err = run_setup("tasks", "--json")
assert_rc(2, rc, "tasks blocks without plan.md", out, err)

# 10. tasks --json succeeds with spec.md + plan.md and resolves tasks template
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True)
rc, out, err = run_setup("tasks", "--json")
assert_rc(0, rc, "tasks succeeds with spec and plan", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"] == str(fdir.resolve()), "tasks JSON includes FEATURE_DIR")
assert_true(data["TASKS_TEMPLATE"].endswith(".orderspec/framework/templates/tasks-template.md"), "tasks JSON includes resolved TASKS_TEMPLATE")

# 11. code --json blocks without tasks.md
reset_repo()
make_feature("specs/F", spec=True, plan=True, tasks=False)
rc, out, err = run_setup("code", "--json")
assert_rc(2, rc, "code blocks without tasks.md", out, err)

# 12. code --json succeeds with feature dir + plan.md + tasks.md
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True, tasks=True)
rc, out, err = run_setup("code", "--json")
assert_rc(0, rc, "code succeeds with plan and tasks", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"] == str(fdir.resolve()), "code JSON includes FEATURE_DIR")
assert_true("tasks.md" in data["AVAILABLE_DOCS"], "code AVAILABLE_DOCS includes tasks.md")

# 13. spec --json blocks when feature dir is missing
reset_repo()
set_active_feature_state("specs/F")
rc, out, err = run_setup("spec", "--json")
assert_rc(2, rc, "spec setup blocks when feature dir missing", out, err)

# 14. spec --json succeeds when feature dir exists and reports SPEC_EXISTS=false
reset_repo()
fdir = WORK / "specs" / "F"
fdir.mkdir(parents=True, exist_ok=True)
set_active_feature_state("specs/F")
rc, out, err = run_setup("spec", "--json")
assert_rc(0, rc, "spec setup succeeds with existing feature dir", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"] == str(fdir.resolve()), "spec JSON includes FEATURE_DIR")
assert_true(data["SPEC_EXISTS"] is False, "spec JSON reports SPEC_EXISTS=false")

# 15. spec --json reports SPEC_EXISTS=true
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=False)
rc, out, err = run_setup("spec", "--json")
assert_rc(0, rc, "spec setup succeeds with spec.md", out, err)
data = parse_json_stdout(out)
assert_true(data["SPEC_EXISTS"] is True, "spec JSON reports SPEC_EXISTS=true")


# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)