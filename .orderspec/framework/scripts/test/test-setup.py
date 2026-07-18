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

# 1. paths rejects missing canonical active-feature state and stays read-only
reset_repo()
env = {"SPECIFY_FEATURE_DIRECTORY": "specs/F"}
rc, out, err = run_setup("paths", "--json", env=env)
assert_rc(2, rc, "paths ignores ambient feature override without active state", out, err)
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
assert_true("FEATURE_DIR_REL" in data, "plan JSON includes FEATURE_DIR_REL key")
assert_true(data["FEATURE_DIR_REL"] == "specs/F", "plan JSON FEATURE_DIR_REL is relative path")
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

# 7. ambient SPECIFY_FEATURE_DIRECTORY cannot override canonical active state
reset_repo()
active_dir = make_feature("specs/F", spec=True, plan=False)
env = {"SPECIFY_FEATURE_DIRECTORY": "features/custom-F"}
fdir = WORK / "features" / "custom-F"
fdir.mkdir(parents=True, exist_ok=True)
(fdir / "spec.md").write_text("# Spec\n- **REQ-001**: System MUST work\n", encoding="utf-8")
rc, out, err = run_setup("plan", "--json", env=env)
assert_rc(0, rc, "ambient feature override is ignored", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"] == str(active_dir.resolve()), "canonical active feature remains target")
assert_true(data["FEATURE_DIR_REL"] == "specs/F", "FEATURE_DIR_REL comes from active state")
assert_true(not (fdir / "plan.md").exists(), "ambient override target is untouched")
state = json.loads((WORK / ".orderspec" / "state" / "active-feature.json").read_text(encoding="utf-8"))
assert_true(
    state["feature_directory"] == "specs/F",
    "active-feature state is unchanged",
)

# 8. active-feature state fallback works when env var is absent
reset_repo()
fdir = make_feature("features/custom-F", spec=True, plan=False)
rc, out, err = run_setup("paths", "--json")
assert_rc(0, rc, "paths falls back to active-feature state", out, err)
data = parse_json_stdout(out)
assert_true(data["FEATURE_DIR"] == str(fdir.resolve()), "active-feature state fallback resolves FEATURE_DIR")
assert_true("FEATURE_DIR_REL" in data, "active-feature fallback returns FEATURE_DIR_REL key")
assert_true(data["FEATURE_DIR_REL"] == "features/custom-F", "active-feature fallback FEATURE_DIR_REL is relative path")

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


# 16. plan-check --json creates a report target when spec.md is missing
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
set_active_feature_state("specs/F")
(WORK / "specs" / "F").mkdir(parents=True, exist_ok=True)
(WORK / "specs" / "F" / "plan.md").write_text("PLAN\n", encoding="utf-8")
rc, out, err = run_setup("plan-check", "--json")
assert_rc(0, rc, "plan-check prepares report without spec.md", out, err)
data = parse_json_stdout(out)
assert_true(data["SPEC_EXISTS"] is False, "plan-check reports SPEC_EXISTS=false")
assert_true(data["PLAN_EXISTS"] is True, "plan-check reports PLAN_EXISTS=true")
assert_true((WORK / "specs" / "F" / "plan-report.md").is_file(), "plan-check creates report target without spec.md")

# 17. plan-check --json creates a report target when plan.md is missing
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=False)
rc, out, err = run_setup("plan-check", "--json")
assert_rc(0, rc, "plan-check prepares report without plan.md", out, err)
data = parse_json_stdout(out)
assert_true(data["SPEC_EXISTS"] is True, "plan-check reports SPEC_EXISTS=true")
assert_true(data["PLAN_EXISTS"] is False, "plan-check reports PLAN_EXISTS=false")
assert_true((fdir / "plan-report.md").is_file(), "plan-check creates report target without plan.md")

# 18. plan-check --json creates plan-report.md from core report template when spec+plan exist
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=True)
rc, out, err = run_setup("plan-check", "--json")
assert_rc(0, rc, "plan-check creates plan-report.md when spec+plan exist", out, err)
data = parse_json_stdout(out)
assert_true((fdir / "plan-report.md").read_text(encoding="utf-8") == "CORE REPORT TEMPLATE\n", "plan-report.md copied from core report template")
assert_true(data["PLAN_REPORT"].endswith("plan-report.md"), "plan-check JSON includes PLAN_REPORT")
assert_true(data["PLAN_REPORT_EXISTS"] is True, "plan-check JSON reports PLAN_REPORT_EXISTS=true")
assert_true(data["REPORT_REFRESHED"] is False, "plan-check JSON reports REPORT_REFRESHED=false without flag")

# 19. plan-check --json does not overwrite existing report without --refresh-template
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=True)
(fdir / "plan-report.md").write_text("EXISTING REPORT\n", encoding="utf-8")
rc, out, err = run_setup("plan-check", "--json")
assert_rc(0, rc, "plan-check preserves existing report without refresh", out, err)
assert_true((fdir / "plan-report.md").read_text(encoding="utf-8") == "EXISTING REPORT\n", "existing plan-report.md preserved")

# 20. plan-check --json --refresh-template overwrites existing report
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=True)
(fdir / "plan-report.md").write_text("EXISTING REPORT\n", encoding="utf-8")
rc, out, err = run_setup("plan-check", "--json", "--refresh-template")
assert_rc(0, rc, "plan-check refresh exits zero", out, err)
assert_true((fdir / "plan-report.md").read_text(encoding="utf-8") == "CORE REPORT TEMPLATE\n", "refresh replaces existing report with template")
data = parse_json_stdout(out)
assert_true(data["REPORT_REFRESHED"] is True, "plan-check JSON marks REPORT_REFRESHED=true")

# 21. plan-check --json --shell-vars outputs eval-ready variables
reset_repo()
write_core_template("report-template", "CORE\n")
fdir = make_feature("specs/F", spec=True, plan=True)
rc, out, err = run_setup("plan-check", "--shell-vars")
assert_rc(0, rc, "plan-check --shell-vars exits zero", out, err)
assert_true("FEATURE_DIR=" in out, "plan-check --shell-vars includes FEATURE_DIR")
assert_true("PLAN_REPORT=" in out, "plan-check --shell-vars includes PLAN_REPORT")

# 22. tasks --json creates tasks.md from core template when spec+plan exist
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True, tasks=False)
rc, out, err = run_setup("tasks", "--json")
assert_rc(0, rc, "tasks creates tasks.md when spec+plan exist", out, err)
assert_true((fdir / "tasks.md").read_text(encoding="utf-8") == "CORE TASKS TEMPLATE\n", "tasks.md copied from core template")
data = parse_json_stdout(out)
assert_true(data["TASKS_REFRESHED"] is False, "tasks JSON marks TASKS_REFRESHED=false without flag")

# 23. tasks --json does not overwrite existing tasks without --refresh-template
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True, tasks=True)
# Overwrite tasks.md with custom content to verify preservation
(fdir / "tasks.md").write_text("EXISTING TASKS\n", encoding="utf-8")
rc, out, err = run_setup("tasks", "--json")
assert_rc(0, rc, "tasks preserves existing tasks without refresh", out, err)
assert_true((fdir / "tasks.md").read_text(encoding="utf-8") == "EXISTING TASKS\n", "existing tasks content preserved")

# 24. tasks --json --refresh-template overwrites existing tasks
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True, tasks=True)
# tasks.md already created by make_feature with "# Tasks\n"
rc, out, err = run_setup("tasks", "--json", "--refresh-template")
assert_rc(0, rc, "tasks refresh exits zero", out, err)
assert_true((fdir / "tasks.md").read_text(encoding="utf-8") == "CORE TASKS TEMPLATE\n", "refresh replaces existing tasks with template")
data = parse_json_stdout(out)
assert_true(data["TASKS_REFRESHED"] is True, "tasks JSON marks TASKS_REFRESHED=true")

# 25. tasks --json --shell-vars outputs eval-ready variables
reset_repo()
fdir = make_feature("specs/F", spec=True, plan=True, tasks=False)
rc, out, err = run_setup("tasks", "--shell-vars")
assert_rc(0, rc, "tasks --shell-vars exits zero", out, err)
assert_true("FEATURE_DIR=" in out, "tasks --shell-vars includes FEATURE_DIR")

# 26. tasks --json blocks when spec.md is missing (but plan.md exists)
reset_repo()
fdir = WORK / "specs" / "F"
fdir.mkdir(parents=True, exist_ok=True)
(fdir / "plan.md").write_text("PLAN\n", encoding="utf-8")
set_active_feature_state("specs/F")
rc, out, err = run_setup("tasks", "--json")
assert_rc(2, rc, "tasks blocks without spec.md", out, err)

# 27. tasks --json blocks when both spec.md and plan.md are missing
reset_repo()
set_active_feature_state("specs/F")
rc, out, err = run_setup("tasks", "--json")
assert_rc(2, rc, "tasks blocks without spec and plan", out, err)

# 28. tasks --json --refresh-template creates feature dir if missing
reset_repo()
# Create spec.md and plan.md but not the feature dir itself
WORK.joinpath("specs", "F").mkdir(parents=True, exist_ok=True)
WORK.joinpath("specs", "F", "spec.md").write_text("# Spec\n", encoding="utf-8")
WORK.joinpath("specs", "F", "plan.md").write_text("PLAN\n", encoding="utf-8")
set_active_feature_state("specs/F")
rc, out, err = run_setup("tasks", "--json", "--refresh-template")
assert_rc(0, rc, "tasks creates tasks.md even if feature dir was partial", out, err)
assert_true((WORK / "specs" / "F" / "tasks.md").exists(), "tasks.md created in feature dir")

# 29. tasks override template wins over core template
reset_repo()
write_override_template("tasks-template", "OVERRIDE TASKS TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=True, tasks=False)
rc, out, err = run_setup("tasks", "--json", "--refresh-template")
assert_rc(0, rc, "tasks with override exits zero", out, err)
assert_true((fdir / "tasks.md").read_text(encoding="utf-8") == "OVERRIDE TASKS TEMPLATE\n", "override tasks-template wins")

# 30. tasks-check prepares a report when spec.md is missing
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
set_active_feature_state("specs/F")
(WORK / "specs" / "F").mkdir(parents=True, exist_ok=True)
(WORK / "specs" / "F" / "plan.md").write_text("PLAN\n", encoding="utf-8")
(WORK / "specs" / "F" / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
rc, out, err = run_setup("tasks-check", "--json")
assert_rc(0, rc, "tasks-check prepares report without spec.md", out, err)
data = parse_json_stdout(out)
assert_true(data["SPEC_EXISTS"] is False, "tasks-check reports missing spec.md")
assert_true((WORK / "specs" / "F" / "tasks-report.md").is_file(), "tasks-check creates report without spec.md")

# 31. tasks-check prepares a report when plan.md is missing
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
make_feature("specs/F", spec=True, plan=False)
(WORK / "specs" / "F" / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
rc, out, err = run_setup("tasks-check", "--json")
assert_rc(0, rc, "tasks-check prepares report without plan.md", out, err)
data = parse_json_stdout(out)
assert_true(data["PLAN_EXISTS"] is False, "tasks-check reports missing plan.md")

# 32. tasks-check prepares a report when tasks.md is missing
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
make_feature("specs/F", spec=True, plan=True, tasks=False)
rc, out, err = run_setup("tasks-check", "--json")
assert_rc(0, rc, "tasks-check prepares report without tasks.md", out, err)
data = parse_json_stdout(out)
assert_true(data["TASKS_EXISTS"] is False, "tasks-check reports missing tasks.md")

# 33. tasks-check --json creates tasks-report.md from core report template when spec+plan+tasks exist
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=True, tasks=True)
rc, out, err = run_setup("tasks-check", "--json")
assert_rc(0, rc, "tasks-check creates tasks-report.md when spec+plan+tasks exist", out, err)
data = parse_json_stdout(out)
assert_true((fdir / "tasks-report.md").read_text(encoding="utf-8") == "CORE REPORT TEMPLATE\n", "tasks-report.md copied from core report template")
assert_true(data["TASKS_REPORT"].endswith("tasks-report.md"), "tasks-check JSON includes TASKS_REPORT")
assert_true(data["TASKS_REPORT_EXISTS"] is True, "tasks-check JSON reports TASKS_REPORT_EXISTS=true")
assert_true(data["REPORT_REFRESHED"] is False, "tasks-check JSON reports REPORT_REFRESHED=false without flag")

# 34. tasks-check --json does not overwrite existing report without --refresh-template
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=True, tasks=True)
(fdir / "tasks-report.md").write_text("EXISTING REPORT\n", encoding="utf-8")
rc, out, err = run_setup("tasks-check", "--json")
assert_rc(0, rc, "tasks-check preserves existing report without refresh", out, err)
assert_true((fdir / "tasks-report.md").read_text(encoding="utf-8") == "EXISTING REPORT\n", "existing tasks-report.md preserved")

# 35. tasks-check --json --refresh-template overwrites existing report
reset_repo()
write_core_template("report-template", "CORE REPORT TEMPLATE\n")
fdir = make_feature("specs/F", spec=True, plan=True, tasks=True)
(fdir / "tasks-report.md").write_text("EXISTING REPORT\n", encoding="utf-8")
rc, out, err = run_setup("tasks-check", "--json", "--refresh-template")
assert_rc(0, rc, "tasks-check refresh exits zero", out, err)
assert_true((fdir / "tasks-report.md").read_text(encoding="utf-8") == "CORE REPORT TEMPLATE\n", "refresh replaces existing report with template")
data = parse_json_stdout(out)
assert_true(data["REPORT_REFRESHED"] is True, "tasks-check JSON marks REPORT_REFRESHED=true")

# 36. tasks-check --json --shell-vars outputs eval-ready variables
reset_repo()
write_core_template("report-template", "CORE\n")
fdir = make_feature("specs/F", spec=True, plan=True, tasks=True)
rc, out, err = run_setup("tasks-check", "--shell-vars")
assert_rc(0, rc, "tasks-check --shell-vars exits zero", out, err)
assert_true("FEATURE_DIR=" in out, "tasks-check --shell-vars includes FEATURE_DIR")
assert_true("TASKS_REPORT=" in out, "tasks-check --shell-vars includes TASKS_REPORT")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
