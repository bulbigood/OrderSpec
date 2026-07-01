#!/usr/bin/env python3
"""test-active-feature.py — regression for active_feature.py state manager"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))
from common import FEATURES_DIR

PY = sys.executable
ACTIVE = SCRIPT_DIR.parent / "active_feature.py"

if not ACTIVE.exists():
    print(f"FATAL: active_feature.py not found at {ACTIVE}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────
LOG_TO_FILE = False  # Set to True to also write test results to test/test-active-feature.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-active-feature.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-active-feature-test-"))

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


def fresh_work(name="case"):
    root = WORK / name
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_active(root, *args):
    cmd = [PY, str(ACTIVE), "-C", str(root)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_json(root, *args):
    rc, out, err = run_active(root, *args)
    try:
        data = json.loads(out)
    except Exception as exc:
        bad(f"invalid JSON output :: args={args} rc={rc} out={out!r} err={err!r} exc={exc}")
        return rc, {}, err
    return rc, data, err


def assert_ok_json(root, name, *args):
    rc, data, err = run_json(root, *args)
    if rc == 0 and data.get("ok") is True:
        ok(name)
    else:
        bad(f"{name} :: rc={rc} data={data!r} err={err!r}")
    return rc, data, err


def assert_error_json(root, expected_error, name, *args):
    rc, data, err = run_json(root, *args)
    if rc != 0 and data.get("ok") is False and data.get("error") == expected_error:
        ok(name)
    else:
        bad(f"{name} :: rc={rc} want_error={expected_error!r} data={data!r} err={err!r}")
    return rc, data, err


def write_spec(root, feature_dir, feature_id="FEAT-001-user-auth", slug="user-auth"):
    fdir = root / feature_dir
    fdir.mkdir(parents=True, exist_ok=True)
    (fdir / "spec.md").write_text(
        "---\n"
        "orderspec:\n"
        "  artifact: spec\n"
        f"  feature_id: \"{feature_id}\"\n"
        f"  slug: \"{slug}\"\n"
        "  status: draft\n"
        "---\n"
        "# Test Spec\n",
        encoding="utf-8",
    )
    return fdir


def write_file(root, rel_path, content):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def active_state_path(root):
    return root / ".orderspec" / "state" / "active-feature.json"


# ── Tests ────────────────────────────────────────────────────────────────────

# 1. script compiles
compile_proc = subprocess.run(
    [PY, "-m", "py_compile", str(ACTIVE)],
    capture_output=True,
    text=True,
)
if compile_proc.returncode == 0:
    ok("active_feature.py py_compile passes")
else:
    bad(f"active_feature.py py_compile fails :: {compile_proc.stderr or compile_proc.stdout}")


# 2. missing state validates as inactive
root = fresh_work("missing-state")
rc, data, err = assert_ok_json(root, "missing state validates as inactive", "validate", "--json")
state = data.get("state", {})
if data.get("active") is False and state.get("status") == "unknown":
    ok("missing state normalized to inactive unknown")
else:
    bad(f"missing state normalization wrong :: {data!r}")


# 3. clear writes canonical inactive state
root = fresh_work("clear")
rc, data, err = assert_ok_json(root, "clear writes inactive state", "clear", "--last-command", "order.spec", "--json")
state = data.get("state", {})
if (
    data.get("active") is False
    and state.get("version") == 1
    and state.get("active") is False
    and state.get("feature_id") is None
    and state.get("feature_directory") is None
    and state.get("status") == "unknown"
    and "slug" not in state
):
    ok("clear state shape is canonical")
else:
    bad(f"clear state shape wrong :: {data!r}")


# 4. set valid FEAT feature_id succeeds
root = fresh_work("set-valid")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "set valid FEAT feature_id succeeds",
    "set",
    "--feature-id",
    "FEAT-001-user-auth",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "specified",
    "--last-command",
    "order.spec",
    "--json",
)
state = data.get("state", {})
if (
    state.get("feature_id") == "FEAT-001-user-auth"
    and state.get("feature_directory") == ".orderspec/features/001-user-auth"
    and state.get("spec_file") == ".orderspec/features/001-user-auth/spec.md"
    and state.get("status") == "specified"
    and "slug" not in state
):
    ok("set valid state metadata correct")
else:
    bad(f"set valid state metadata wrong :: {data!r}")


# 5. set invalid TASKS feature_id rejected
root = fresh_work("set-invalid-tasks")
(root / ".orderspec/features/001-user-auth").mkdir(parents=True)
assert_error_json(
    root,
    "invalid_active_feature",
    "set invalid TASKS feature_id rejected",
    "set",
    "--feature-id",
    "TASKS-001",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "specified",
    "--json",
)


# 6. set invalid directory-style feature_id rejected
root = fresh_work("set-invalid-dirname")
(root / ".orderspec/features/001-user-auth").mkdir(parents=True)
assert_error_json(
    root,
    "invalid_active_feature",
    "set invalid directory-style feature_id rejected",
    "set",
    "--feature-id",
    "001-user-auth",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "specified",
    "--json",
)


# 7. set invalid lowercase feat rejected
root = fresh_work("set-invalid-lowercase")
(root / ".orderspec/features/001-user-auth").mkdir(parents=True)
assert_error_json(
    root,
    "invalid_active_feature",
    "set lowercase feat feature_id rejected",
    "set",
    "--feature-id",
    "feat-001-user-auth",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "specified",
    "--json",
)


# 8. set without explicit feature_id infers valid FEAT from spec.md
root = fresh_work("set-infer-from-spec")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "set infers valid FEAT feature_id from spec.md",
    "set",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "specified",
    "--json",
)
if data.get("state", {}).get("feature_id") == "FEAT-001-user-auth":
    ok("set inferred FEAT feature_id correctly")
else:
    bad(f"set inferred feature_id wrong :: {data!r}")


# 9. set without explicit feature_id rejects invalid inferred directory fallback
root = fresh_work("set-invalid-inferred-fallback")
(root / ".orderspec/features/001-user-auth").mkdir(parents=True)
assert_error_json(
    root,
    "invalid_active_feature",
    "set rejects invalid inferred directory fallback feature_id",
    "set",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "specified",
    "--json",
)


# 10. validate rejects persisted invalid active feature_id
root = fresh_work("validate-invalid-persisted")
state_file = root / ".orderspec/state/active-feature.json"
state_file.parent.mkdir(parents=True, exist_ok=True)
state_file.write_text(
    json.dumps(
        {
            "version": 1,
            "active": True,
            "feature_id": "TASKS-001",
            "feature_directory": ".orderspec/features/001-user-auth",
            "spec_file": None,
            "plan_file": None,
            "tasks_file": None,
            "status": "specified",
            "last_command": "order.spec",
            "updated_at": "2026-06-28T00:00:00Z",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
rc, data, err = run_json(root, "validate", "--json")
errors = data.get("validation_errors", [])
if rc != 0 and any("feature_id must match FEAT-NNN-slug" in e for e in errors):
    ok("validate rejects persisted invalid feature_id")
else:
    bad(f"validate did not reject invalid feature_id :: rc={rc} data={data!r} err={err!r}")


# 11. list reads FEAT feature_id from spec frontmatter
root = fresh_work("list")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(root, "list succeeds", "list", "--json")
features = data.get("features", [])
if len(features) == 1 and features[0].get("feature_id") == "FEAT-001-user-auth":
    ok("list reads FEAT feature_id from spec frontmatter")
else:
    bad(f"list feature_id wrong :: {data!r}")


# 12. select by FEAT feature_id succeeds
root = fresh_work("select-by-feature-id")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "select by FEAT feature_id succeeds",
    "select",
    "FEAT-001-user-auth",
    "--last-command",
    "order.spec",
    "--json",
)
state = data.get("state", {})
if (
    state.get("feature_id") == "FEAT-001-user-auth"
    and state.get("feature_directory") == ".orderspec/features/001-user-auth"
    and state.get("status") == "specified"
):
    ok("select by FEAT state metadata correct")
else:
    bad(f"select by FEAT state metadata wrong :: {data!r}")


# 13. select by directory basename succeeds when spec has FEAT id
root = fresh_work("select-by-dirname")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "select by directory basename succeeds",
    "select",
    "001-user-auth",
    "--last-command",
    "order.spec",
    "--json",
)
if data.get("state", {}).get("feature_id") == "FEAT-001-user-auth":
    ok("select by directory basename preserves FEAT feature_id")
else:
    bad(f"select by directory basename wrong :: {data!r}")


# 14. unsafe feature_directory rejected
root = fresh_work("unsafe-feature-directory")
assert_error_json(
    root,
    "invalid_active_feature",
    "unsafe feature_directory rejected",
    "set",
    "--feature-id",
    "FEAT-001-user-auth",
    "--feature-directory",
    "../specs/001-user-auth",
    "--status",
    "specified",
    "--json",
)


# 15. invalid status rejected by argparse
root = fresh_work("invalid-status")
rc, out, err = run_active(
    root,
    "set",
    "--feature-id",
    "FEAT-001-user-auth",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "draft",
    "--json",
)
if rc != 0 and "invalid choice" in err:
    ok("invalid active feature status rejected by argparse")
else:
    bad(f"invalid status not rejected as expected :: rc={rc} out={out!r} err={err!r}")



# ── Additional active_feature behavior regressions ───────────────────────────

# 16. get after set returns persisted active feature
root = fresh_work("get-after-set")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
assert_ok_json(
    root,
    "get-after-set setup succeeds",
    "set",
    "--feature-id",
    "FEAT-001-user-auth",
    "--feature-directory",
    ".orderspec/features/001-user-auth",
    "--status",
    "specified",
    "--last-command",
    "order.spec",
    "--json",
)
rc, data, err = assert_ok_json(root, "get after set succeeds", "get", "--json")
state = data.get("state", {})
if (
    data.get("exists") is True
    and data.get("active") is True
    and state.get("feature_id") == "FEAT-001-user-auth"
    and state.get("feature_directory") == ".orderspec/features/001-user-auth"
    and state.get("status") == "specified"
):
    ok("get after set returns persisted active feature")
else:
    bad(f"get after set state wrong :: {data!r}")


# 17. validate passes for valid active state
rc, data, err = assert_ok_json(root, "validate valid active state succeeds", "validate", "--json")
if data.get("validation_errors") == []:
    ok("validate passes for valid active state")
else:
    bad(f"validate valid state reported errors :: {data!r}")


# 18. select by feature directory path
root = fresh_work("select-by-path")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "select by feature directory path succeeds",
    "select",
    ".orderspec/features/001-user-auth",
    "--last-command",
    "order.spec",
    "--json",
)
if data.get("state", {}).get("feature_id") == "FEAT-001-user-auth":
    ok("select by feature directory path preserves FEAT feature_id")
else:
    bad(f"select by feature directory path wrong :: {data!r}")


# 19. select by short numeric prefix
root = fresh_work("select-by-short-prefix")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "select by short numeric prefix succeeds",
    "select",
    "001",
    "--last-command",
    "order.spec",
    "--json",
)
if data.get("state", {}).get("feature_id") == "FEAT-001-user-auth":
    ok("select by short numeric prefix preserves FEAT feature_id")
else:
    bad(f"select by short numeric prefix wrong :: {data!r}")


# 20. ambiguous short prefix is rejected
root = fresh_work("ambiguous-prefix")
write_spec(root, ".orderspec/features/003-alpha", feature_id="FEAT-003-alpha", slug="alpha")
write_spec(root, ".orderspec/features/003-beta", feature_id="FEAT-003-beta", slug="beta")
rc, data, err = run_json(root, "select", "003", "--json")
if rc != 0 and data.get("error") == "ambiguous_feature" and len(data.get("matches", [])) == 2:
    ok("ambiguous short prefix rejected")
else:
    bad(f"ambiguous short prefix not rejected as expected :: rc={rc} data={data!r} err={err!r}")


# 21. list discovers only feature directories with spec.md
root = fresh_work("list-filters")
write_spec(root, ".orderspec/features/001-alpha", feature_id="FEAT-001-alpha", slug="alpha")
write_spec(root, ".orderspec/features/002-beta", feature_id="FEAT-002-beta", slug="beta")
(root / FEATURES_DIR / "999-not-a-feature").mkdir(parents=True)
write_file(root, ".orderspec/features/999-not-a-feature/README.md", "not a feature\n")
rc, data, err = assert_ok_json(root, "list filters setup succeeds", "list", "--json")
ids = {f.get("feature_id") for f in data.get("features", [])}
if data.get("count") == 2 and ids == {"FEAT-001-alpha", "FEAT-002-beta"}:
    ok("list discovers only feature directories with spec.md")
else:
    bad(f"list filtering wrong :: {data!r}")


# 22. status inference: spec only => specified
root = fresh_work("status-specified")
write_spec(root, ".orderspec/features/001-alpha", feature_id="FEAT-001-alpha", slug="alpha")
rc, data, err = assert_ok_json(root, "status specified select succeeds", "select", "001-alpha", "--json")
if data.get("state", {}).get("status") == "specified":
    ok("status inference spec only => specified")
else:
    bad(f"status inference specified wrong :: {data!r}")


# 23. status inference: plan.md exists => planned
root = fresh_work("status-planned")
write_spec(root, ".orderspec/features/001-alpha", feature_id="FEAT-001-alpha", slug="alpha")
write_file(root, ".orderspec/features/001-alpha/plan.md", "# Plan\n")
rc, data, err = assert_ok_json(root, "status planned select succeeds", "select", "001-alpha", "--json")
state = data.get("state", {})
if state.get("status") == "planned" and state.get("plan_file") == ".orderspec/features/001-alpha/plan.md":
    ok("status inference plan.md => planned")
else:
    bad(f"status inference planned wrong :: {data!r}")


# 24. status inference: tasks.md exists => tasks
root = fresh_work("status-tasks")
write_spec(root, ".orderspec/features/001-alpha", feature_id="FEAT-001-alpha", slug="alpha")
write_file(root, ".orderspec/features/001-alpha/plan.md", "# Plan\n")
write_file(root, ".orderspec/features/001-alpha/tasks.md", "# Tasks\n")
rc, data, err = assert_ok_json(root, "status tasks select succeeds", "select", "001-alpha", "--json")
state = data.get("state", {})
if state.get("status") == "tasks" and state.get("tasks_file") == ".orderspec/features/001-alpha/tasks.md":
    ok("status inference tasks.md => tasks")
else:
    bad(f"status inference tasks wrong :: {data!r}")


# 25. invalid JSON state is rejected by get
root = fresh_work("invalid-json-state")
state_file = active_state_path(root)
state_file.parent.mkdir(parents=True, exist_ok=True)
state_file.write_text("{not json\n", encoding="utf-8")
rc, data, err = run_json(root, "get", "--json")
if rc != 0 and data.get("ok") is False and any("invalid JSON" in e for e in data.get("validation_errors", [])):
    ok("get rejects invalid JSON state")
else:
    bad(f"invalid JSON state not rejected :: rc={rc} data={data!r} err={err!r}")


# 26. malformed active state is rejected by validate
root = fresh_work("malformed-state")
state_file = active_state_path(root)
state_file.parent.mkdir(parents=True, exist_ok=True)
state_file.write_text(
    json.dumps(
        {
            "version": 1,
            "active": True,
            "feature_directory": ".orderspec/features/001-alpha",
            "status": "specified",
            "last_command": "order.spec",
            "updated_at": "2026-06-29T00:00:00Z",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
rc, data, err = run_json(root, "validate", "--json")
if rc != 0 and any("feature_id" in e for e in data.get("validation_errors", [])):
    ok("validate rejects malformed active state")
else:
    bad(f"malformed active state not rejected :: rc={rc} data={data!r} err={err!r}")


# 27. validate rejects state pointing to deleted feature directory
root = fresh_work("deleted-feature-directory")
write_spec(root, ".orderspec/features/001-alpha", feature_id="FEAT-001-alpha", slug="alpha")
assert_ok_json(
    root,
    "deleted feature setup select succeeds",
    "select",
    "001-alpha",
    "--last-command",
    "order.spec",
    "--json",
)
shutil.rmtree(root / FEATURES_DIR / "001-alpha", ignore_errors=True)
rc, data, err = run_json(root, "validate", "--json")
if rc != 0 and any("feature_directory does not exist" in e for e in data.get("validation_errors", [])):
    ok("validate rejects deleted feature directory")
else:
    bad(f"validate did not reject deleted feature directory :: rc={rc} data={data!r} err={err!r}")


# 28. validate rejects missing spec_file when state claims it exists
root = fresh_work("missing-spec-file")
(root / FEATURES_DIR / "001-alpha").mkdir(parents=True)
state_file = active_state_path(root)
state_file.parent.mkdir(parents=True, exist_ok=True)
state_file.write_text(
    json.dumps(
        {
            "version": 1,
            "active": True,
            "feature_id": "FEAT-001-alpha",
            "feature_directory": ".orderspec/features/001-alpha",
            "spec_file": ".orderspec/features/001-alpha/spec.md",
            "plan_file": None,
            "tasks_file": None,
            "status": "specified",
            "last_command": "order.spec",
            "updated_at": "2026-06-29T00:00:00Z",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
rc, data, err = run_json(root, "validate", "--json")
if rc != 0 and any("spec_file does not exist" in e for e in data.get("validation_errors", [])):
    ok("validate rejects missing spec_file")
else:
    bad(f"validate did not reject missing spec_file :: rc={rc} data={data!r} err={err!r}")


# 29. clear --delete removes state file
root = fresh_work("clear-delete")
write_spec(root, ".orderspec/features/001-alpha", feature_id="FEAT-001-alpha", slug="alpha")
assert_ok_json(
    root,
    "clear delete setup select succeeds",
    "select",
    "001-alpha",
    "--last-command",
    "order.spec",
    "--json",
)
rc, data, err = assert_ok_json(root, "clear --delete succeeds", "clear", "--delete", "--json")
if data.get("action") == "deleted" and not active_state_path(root).exists():
    ok("clear --delete removes state file")
else:
    bad(f"clear --delete did not remove state file :: {data!r}")


# 30. list supports custom specs root
root = fresh_work("custom-specs-root-list")
write_spec(root, "features/001-custom", feature_id="FEAT-001-custom", slug="custom")
rc, data, err = assert_ok_json(
    root,
    "custom specs root list succeeds",
    "list",
    "--specs-root",
    "features",
    "--json",
)
features = data.get("features", [])
if data.get("count") == 1 and features[0].get("feature_id") == "FEAT-001-custom":
    ok("list supports custom specs root")
else:
    bad(f"custom specs root list wrong :: {data!r}")


# 31. invalid specs root is rejected
root = fresh_work("invalid-specs-root-list")
rc, data, err = run_json(root, "list", "--specs-root", "../features", "--json")
if rc != 0 and data.get("error") == "invalid_specs_root":
    ok("invalid specs root rejected")
else:
    bad(f"invalid specs root accepted :: rc={rc} data={data!r} err={err!r}")



# 32. resolve by FEAT feature_id is read-only
root = fresh_work("resolve-readonly")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "resolve by FEAT feature_id succeeds",
    "resolve",
    "FEAT-001-user-auth",
    "--json",
)
state = data.get("state", {})
if (
    data.get("action") == "resolved"
    and data.get("state_written") is False
    and state.get("feature_id") == "FEAT-001-user-auth"
    and state.get("feature_directory") == ".orderspec/features/001-user-auth"
    and not active_state_path(root).exists()
):
    ok("resolve by FEAT feature_id is read-only")
else:
    bad(f"resolve by FEAT feature_id wrong or wrote state :: {data!r}")


# 33. resolve by directory basename is read-only
root = fresh_work("resolve-by-dirname")
write_spec(root, ".orderspec/features/001-user-auth", feature_id="FEAT-001-user-auth", slug="user-auth")
rc, data, err = assert_ok_json(
    root,
    "resolve by directory basename succeeds",
    "resolve",
    "001-user-auth",
    "--json",
)
if (
    data.get("state", {}).get("feature_id") == "FEAT-001-user-auth"
    and data.get("state_written") is False
    and not active_state_path(root).exists()
):
    ok("resolve by directory basename is read-only")
else:
    bad(f"resolve by directory basename wrong or wrote state :: {data!r}")


# 34. resolve ambiguous short prefix is rejected without writing state
root = fresh_work("resolve-ambiguous-prefix")
write_spec(root, ".orderspec/features/003-alpha", feature_id="FEAT-003-alpha", slug="alpha")
write_spec(root, ".orderspec/features/003-beta", feature_id="FEAT-003-beta", slug="beta")
rc, data, err = run_json(root, "resolve", "003", "--json")
if (
    rc != 0
    and data.get("error") == "ambiguous_feature"
    and len(data.get("matches", [])) == 2
    and not active_state_path(root).exists()
):
    ok("resolve ambiguous short prefix rejected without writing state")
else:
    bad(f"resolve ambiguous prefix wrong :: rc={rc} data={data!r} err={err!r}")


# 35. resolve invalid specs root is rejected
root = fresh_work("resolve-invalid-specs-root")
rc, data, err = run_json(root, "resolve", "anything", "--specs-root", "../features", "--json")
if rc != 0 and data.get("error") == "invalid_specs_root":
    ok("resolve invalid specs root rejected")
else:
    bad(f"resolve invalid specs root accepted :: rc={rc} data={data!r} err={err!r}")


# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
