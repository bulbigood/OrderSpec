#!/usr/bin/env python3
"""test-feature-spec.py — regression for feature_spec.py allocator"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
FEATURE_SPEC = SCRIPT_DIR.parent / "feature_spec.py"

if not FEATURE_SPEC.exists():
    print(f"FATAL: feature_spec.py not found at {FEATURE_SPEC}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────
LOG_TO_FILE = False  # Set to True to also write test results to test/test-feature-spec.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-feature-spec.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-feature-spec-test-"))

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


def run_feature(root, *args):
    cmd = [PY, str(FEATURE_SPEC), "-C", str(root)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_json(root, *args):
    rc, out, err = run_feature(root, *args)
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


# ── Tests ────────────────────────────────────────────────────────────────────

# 1. script compiles
compile_proc = subprocess.run(
    [PY, "-m", "py_compile", str(FEATURE_SPEC)],
    capture_output=True,
    text=True,
)
if compile_proc.returncode == 0:
    ok("feature_spec.py py_compile passes")
else:
    bad(f"feature_spec.py py_compile fails :: {compile_proc.stderr or compile_proc.stdout}")


# 2. slugify normalizes punctuation and case
root = fresh_work("slugify-basic")
rc, data, err = assert_ok_json(
    root,
    "slugify normalizes punctuation and case",
    "slugify",
    "User Auth!!!",
    "--json",
)
if data.get("slug") != "user-auth":
    bad(f"slugify output wrong :: {data!r}")
else:
    ok("slugify output is user-auth")


# 3. slugify collapses repeated separators
root = fresh_work("slugify-separators")
rc, data, err = assert_ok_json(
    root,
    "slugify collapses repeated separators",
    "slugify",
    "  Billing___Invoices / Export  ",
    "--json",
)
if data.get("slug") == "billing-invoices-export":
    ok("slugify separator result is stable")
else:
    bad(f"slugify separator result wrong :: {data!r}")


# 4. slugify rejects empty-normalized input
root = fresh_work("slugify-empty")
assert_error_json(
    root,
    "invalid_slug",
    "slugify rejects empty-normalized input",
    "slugify",
    "!!!",
    "--json",
)


# 5. create allocates FEAT-001 and specs/001-*
root = fresh_work("create-first")
rc, data, err = assert_ok_json(
    root,
    "create first feature succeeds",
    "create",
    "--slug",
    "User Auth",
    "--json",
)
if (
    data.get("feature_id") == "FEAT-001-user-auth"
    and data.get("slug") == "user-auth"
    and data.get("feature_number") == "001"
    and data.get("feature_directory") == "specs/001-user-auth"
    and data.get("spec_file") == "specs/001-user-auth/spec.md"
    and data.get("created_directory") is True
    and (root / "specs/001-user-auth").is_dir()
    and not (root / "specs/001-user-auth/spec.md").exists()
):
    ok("create first feature metadata and filesystem are correct")
else:
    bad(f"create first feature metadata/filesystem wrong :: {data!r}")


# 6. create second feature allocates next free number
rc, data, err = assert_ok_json(
    root,
    "create second feature succeeds",
    "create",
    "--slug",
    "Task Audit",
    "--json",
)
if (
    data.get("feature_id") == "FEAT-002-task-audit"
    and data.get("feature_directory") == "specs/002-task-audit"
    and (root / "specs/002-task-audit").is_dir()
):
    ok("create second feature uses next free number")
else:
    bad(f"create second feature numbering wrong :: {data!r}")


# 7. existing non-feature directories are ignored for numbering
root = fresh_work("ignore-non-feature-dirs")
(root / "specs" / "abc-not-a-feature").mkdir(parents=True)
(root / "specs" / "001").mkdir(parents=True)
rc, data, err = assert_ok_json(
    root,
    "create ignores non-feature dirs",
    "create",
    "--slug",
    "Real Feature",
    "--json",
)
if data.get("feature_id") == "FEAT-001-real-feature":
    ok("non-feature dirs do not consume numbers")
else:
    bad(f"non-feature dirs consumed number unexpectedly :: {data!r}")


# 8. gaps are reused: 001 and 003 existing → next is 002
root = fresh_work("reuse-gap")
(root / "specs" / "001-first").mkdir(parents=True)
(root / "specs" / "003-third").mkdir(parents=True)
rc, data, err = assert_ok_json(
    root,
    "create reuses numeric gap",
    "create",
    "--slug",
    "Second",
    "--json",
)
if data.get("feature_id") == "FEAT-002-second":
    ok("numeric gap 002 reused")
else:
    bad(f"numeric gap not reused :: {data!r}")


# 9. explicit number works
root = fresh_work("explicit-number")
rc, data, err = assert_ok_json(
    root,
    "explicit number create succeeds",
    "create",
    "--slug",
    "Manual Number",
    "--number",
    "7",
    "--json",
)
if (
    data.get("feature_id") == "FEAT-007-manual-number"
    and data.get("feature_directory") == "specs/007-manual-number"
    and (root / "specs/007-manual-number").is_dir()
):
    ok("explicit number metadata correct")
else:
    bad(f"explicit number metadata wrong :: {data!r}")


# 10. explicit number lower bound rejected
root = fresh_work("number-zero")
assert_error_json(
    root,
    "invalid_feature_number",
    "explicit number 0 rejected",
    "create",
    "--slug",
    "Bad Number",
    "--number",
    "0",
    "--json",
)


# 11. explicit number upper bound rejected
root = fresh_work("number-thousand")
assert_error_json(
    root,
    "invalid_feature_number",
    "explicit number 1000 rejected",
    "create",
    "--slug",
    "Bad Number",
    "--number",
    "1000",
    "--json",
)


# 12. dry-run returns metadata and creates no directory
root = fresh_work("dry-run")
rc, data, err = assert_ok_json(
    root,
    "dry-run succeeds",
    "create",
    "--slug",
    "Dry Run Feature",
    "--dry-run",
    "--json",
)
if (
    data.get("action") == "dry_run"
    and data.get("created_directory") is False
    and data.get("feature_id") == "FEAT-001-dry-run-feature"
    and data.get("feature_directory") == "specs/001-dry-run-feature"
    and not (root / "specs/001-dry-run-feature").exists()
):
    ok("dry-run does not create directory")
else:
    bad(f"dry-run behavior wrong :: {data!r}")


# 13. collision rejected for same explicit number and slug
root = fresh_work("collision-same")
rc, data, err = assert_ok_json(
    root,
    "collision setup create succeeds",
    "create",
    "--slug",
    "User Auth",
    "--number",
    "1",
    "--json",
)
assert_error_json(
    root,
    "feature_directory_exists",
    "same explicit directory collision rejected",
    "create",
    "--slug",
    "User Auth",
    "--number",
    "1",
    "--json",
)


# 14. existing exact next directory collision is naturally avoided by next_free
root = fresh_work("avoid-existing")
(root / "specs" / "001-existing").mkdir(parents=True)
rc, data, err = assert_ok_json(
    root,
    "allocator skips existing 001",
    "create",
    "--slug",
    "Next",
    "--json",
)
if data.get("feature_id") == "FEAT-002-next":
    ok("allocator skips existing 001")
else:
    bad(f"allocator did not skip existing 001 :: {data!r}")


# 15. unsafe absolute specs-root rejected
root = fresh_work("unsafe-absolute")
assert_error_json(
    root,
    "invalid_specs_root",
    "absolute specs-root rejected",
    "create",
    "--slug",
    "Unsafe",
    "--specs-root",
    "/tmp/specs",
    "--json",
)


# 16. unsafe parent specs-root rejected
root = fresh_work("unsafe-parent")
assert_error_json(
    root,
    "invalid_specs_root",
    "parent traversal specs-root rejected",
    "create",
    "--slug",
    "Unsafe",
    "--specs-root",
    "../specs",
    "--json",
)


# 17. custom safe specs-root works
root = fresh_work("custom-specs-root")
rc, data, err = assert_ok_json(
    root,
    "custom safe specs-root create succeeds",
    "create",
    "--slug",
    "Custom Root",
    "--specs-root",
    "features",
    "--json",
)
if (
    data.get("feature_id") == "FEAT-001-custom-root"
    and data.get("feature_directory") == "features/001-custom-root"
    and (root / "features/001-custom-root").is_dir()
):
    ok("custom safe specs-root metadata correct")
else:
    bad(f"custom safe specs-root metadata wrong :: {data!r}")


# 18. invalid slug after normalization rejected
root = fresh_work("invalid-slug")
assert_error_json(
    root,
    "invalid_slug",
    "invalid slug after normalization rejected",
    "create",
    "--slug",
    "___",
    "--json",
)


# 19. no free feature number rejected when 001..999 are used
root = fresh_work("exhausted")
for i in range(1, 1000):
    (root / "specs" / f"{i:03d}-used").mkdir(parents=True)
assert_error_json(
    root,
    "no_free_feature_number",
    "no free feature number rejected",
    "create",
    "--slug",
    "Overflow",
    "--json",
)


# 20. explicit number collision with existing directory rejected
root = fresh_work("explicit-existing-dir")
(root / "specs" / "005-existing").mkdir(parents=True)
assert_error_json(
    root,
    "feature_directory_exists",
    "explicit number existing directory collision rejected",
    "create",
    "--slug",
    "existing",
    "--number",
    "5",
    "--json",
)


# 21. created_at is present in successful create response
root = fresh_work("created-at")
rc, data, err = assert_ok_json(
    root,
    "created_at create setup succeeds",
    "create",
    "--slug",
    "Timestamped",
    "--json",
)
created_at = data.get("created_at")
if isinstance(created_at, str) and created_at.endswith("Z") and "T" in created_at:
    ok("created_at is ISO-like UTC timestamp")
else:
    bad(f"created_at missing or malformed :: {data!r}")


# 22. feature_id format is uppercase FEAT with lowercase slug
root = fresh_work("feature-id-format")
rc, data, err = assert_ok_json(
    root,
    "feature_id format setup succeeds",
    "create",
    "--slug",
    "Mixed CASE Name",
    "--json",
)
if data.get("feature_id") == "FEAT-001-mixed-case-name":
    ok("feature_id format is FEAT-001-slug")
else:
    bad(f"feature_id format wrong :: {data!r}")


# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)
