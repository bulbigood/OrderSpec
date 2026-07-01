#!/usr/bin/env python3
"""test-lint.py — regression for lint engine"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PY = sys.executable
TRACE = SCRIPT_DIR.parent / "traceability.py"

if not TRACE.exists():
    print(f"FATAL: traceability.py not found at {TRACE}", file=sys.stderr)
    sys.exit(2)

# ── Configuration ────────────────────────────────────────────────────────────
LOG_TO_FILE = False  # Set to True to also write test results to test/test-lint.log

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-lint.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
sys.path.insert(0, str(SCRIPT_DIR.parent))
from common import FEATURES_DIR
SPECS_ROOT = WORK / FEATURES_DIR
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = "F"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".state"
TAB = "\t"

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

def reset_feature():
    if SPECS.exists():
        shutil.rmtree(SPECS, ignore_errors=True)
    SPECS.mkdir(parents=True, exist_ok=True)
    (SPECS / "spec.md").write_text("")
    run_trace("init", F)

def run_trace(*args, input_text=None):
    cmd = [PY, str(TRACE), "-C", str(WORK)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr

def run_lint():
    rc, out, err = run_trace("lint", F)
    return rc, out + err

def mech_hdr():
    return f"#orderspec mechanisms v1\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\n"

def trace_hdr():
    return f"#orderspec traceability v1\nspec_id{TAB}task_ids{TAB}files{TAB}source\n"

def put_mech(content):
    path = SDIR / "mechanisms.tsv"
    path.write_text(content)

def put_trace(content):
    path = SDIR / "traceability.tsv"
    path.write_text(content)

def assert_rc(expected, name):
    rc, out = run_lint()
    if rc == expected:
        ok(name)
    else:
        bad(f"{name} (rc={rc} want {expected}) :: {out}")

# ── Tests ────────────────────────────────────────────────────────────────────

# 1. happy path
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}Task model adds fields{TAB}src/models/task.model.js{TAB}unit\n")
assert_rc(0, "valid mechanisms.tsv passes")

# 2. documented + multi-path is rejected in Configuration B
reset_feature()
put_mech(mech_hdr() + f"NFR-002{TAB}documented{TAB}append only{TAB}src/m/a.js;src/r/v1/t.js{TAB}documented\n")
assert_rc(2, "documented + multi-path rejected")

# 2a. documented + single primary file passes
reset_feature()
put_mech(mech_hdr() + f"NFR-002{TAB}documented{TAB}append only{TAB}plan.md{TAB}documented\n")
assert_rc(0, "documented + single primary file passes")

# 3. wrong marker version
reset_feature()
put_mech(f"#orderspec mechanisms v2\nspec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type\nREQ-001{TAB}direct{TAB}x{TAB}a.js{TAB}unit\n")
assert_rc(2, "wrong marker version rejected")

# 4. wrong column-names row
reset_feature()
put_mech(f"#orderspec mechanisms v1\nspec_id{TAB}cov{TAB}mechanism{TAB}primary_files{TAB}test_type\nREQ-001{TAB}direct{TAB}x{TAB}a.js{TAB}unit\n")
assert_rc(2, "wrong column names rejected")

# 5. missing column-names row
reset_feature()
put_mech("#orderspec mechanisms v1\n")
assert_rc(2, "missing column-names row rejected")

# 6. em-dash test_type (— is U+2014)
reset_feature()
put_mech(mech_hdr() + f"NFR-002{TAB}documented{TAB}append only{TAB}src/x.js{TAB}\u2014\n")
assert_rc(2, "em-dash test_type rejected")

# 7. duplicate spec_id
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\nREQ-001{TAB}direct{TAB}b{TAB}src/b.js{TAB}unit\n")
assert_rc(2, "duplicate spec_id rejected")

# 8. too few columns
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js\n")
assert_rc(2, "too few columns rejected")

# 9. empty mechanism
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}{TAB}src/a.js{TAB}unit\n")
assert_rc(2, "empty mechanism rejected")

# 10. path with space
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a b.js{TAB}unit\n")
assert_rc(2, "path with space rejected")

# 11. CRLF data row
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\r\n")
assert_rc(2, "CRLF data row rejected")

# 12. malformed spec_id
reset_feature()
put_mech(mech_hdr() + f"REQ-1{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
assert_rc(2, "malformed spec_id rejected")

# 13. blank data line
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n\nREQ-002{TAB}direct{TAB}b{TAB}src/b.js{TAB}unit\n")
assert_rc(2, "blank data line rejected")

# 14. wrong .schema version
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
schema = SDIR / ".schema"
schema.write_text("v9\n")
assert_rc(2, "wrong .schema version rejected")

# 15. valid traceability.tsv
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
put_trace(trace_hdr() + f"REQ-001{TAB}T001{TAB}src/a.js{TAB}tasks.md\n")
assert_rc(0, "valid traceability.tsv passes")

# 16. empty task_ids + source=tasks.md → inconsistent
reset_feature()
put_mech(mech_hdr() + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n")
put_trace(trace_hdr() + f"REQ-001{TAB}{TAB}src/a.js{TAB}tasks.md\n")
assert_rc(2, "empty task_ids with source=tasks.md rejected")

# 17. empty task_ids + source=plan.md → OK
reset_feature()
put_mech(mech_hdr() + f"NFR-002{TAB}documented{TAB}append only{TAB}src/a.js{TAB}documented\n")
put_trace(trace_hdr() + f"NFR-002{TAB}{TAB}src/a.js{TAB}plan.md\n")
assert_rc(0, "empty task_ids with source=plan.md passes")

# 18. SC must not have mechanism row
reset_feature()
put_mech(mech_hdr() + f"SC-001{TAB}documented{TAB}release outcome{TAB}plan.md{TAB}documented\n")
assert_rc(2, "SC mechanism row rejected")

# 19. delegated target must exist
reset_feature()
put_mech(mech_hdr() + f"AC-001{TAB}delegated:REQ-001{TAB}delegated{TAB}src/a.js{TAB}unit\n")
assert_rc(2, "delegated target without mechanism row rejected")

# 20. delegated cycle rejected
reset_feature()
put_mech(
    mech_hdr()
    + f"AC-001{TAB}delegated:AC-002{TAB}delegated{TAB}src/a.js{TAB}unit\n"
    + f"AC-002{TAB}delegated:AC-001{TAB}delegated{TAB}src/a.js{TAB}unit\n"
)
assert_rc(2, "delegated cycle rejected")

# 21. summarize-mechanisms --json reports script-derived counts
reset_feature()
put_mech(
    mech_hdr()
    + f"REQ-001{TAB}direct{TAB}a{TAB}src/a.js{TAB}unit\n"
    + f"NFR-001{TAB}documented{TAB}b{TAB}plan.md{TAB}documented\n"
    + f"AC-001{TAB}delegated:REQ-001{TAB}c{TAB}src/a.js{TAB}integration\n"
)
rc, out, err = run_trace("summarize-mechanisms", "--json", F)
try:
    data = json.loads(out)
    if (
        rc == 0
        and data["total"] == 3
        and data["direct"] == 1
        and data["documented"] == 1
        and data["delegated"] == 1
        and data["by_prefix"]["REQ"]["direct"] == 1
    ):
        ok("summarize-mechanisms --json reports counts")
    else:
        bad(f"summarize-mechanisms counts wrong :: rc={rc} out={out!r} err={err!r}")
except Exception as exc:
    bad(f"summarize-mechanisms output invalid :: rc={rc} out={out!r} err={err!r} exc={exc}")

# ── YAML frontmatter tests (M28) ─────────────────────────────────────────────

def write_spec_content(content):
    (SPECS / "spec.md").write_text(content, encoding="utf-8")


def run_validate_spec_json():
    rc, out, err = run_trace("validate", "--stage", "spec", "--json", F)
    try:
        return rc, json.loads(out), err
    except Exception as exc:
        bad(f"validate --json output invalid :: rc={rc} err={err!r} exc={exc} :: {out!r}")
        return rc, {"findings": []}, err


def m28_findings(data):
    return [f for f in data["findings"] if f["check"] == "M28"]


def m28_messages(data):
    return " ".join(f["message"] for f in m28_findings(data))


def m28_flagged_fields(data):
    fields = set()

    for finding in m28_findings(data):
        message = finding["message"]
        if "'" not in message:
            continue

        parts = message.split("'")
        if len(parts) >= 2:
            fields.add(parts[1])

    return fields


# 22. valid new YAML frontmatter → no M28 finding
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-tasks\n"
    "  slug: tasks-001\n"
    "  status: draft\n"
    "  refs:\n"
    "    framework_rules: \".orderspec/framework/orderspec-rules.md\"\n"
    "    constitution: \"constitution.md\"\n"
    "    stack: \"stack.md\"\n"
    "    architecture: \"architecture.md\"\n"
    "    conventions: \"conventions.md\"\n"
    "  generator:\n"
    "    command: order.spec\n"
    "    prompt_version: \"1.0.0\"\n"
    "    model_tier: \"medium\"\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
m28 = m28_findings(data)
if not m28:
    ok("valid new YAML frontmatter → no M28 finding")
else:
    bad(f"M28 false positive on valid new frontmatter :: {m28}")


# 23. missing YAML frontmatter → M28 finding
reset_feature()
write_spec_content(
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
m28 = m28_findings(data)
if m28 and any("No YAML frontmatter" in f["message"] for f in m28):
    ok("missing YAML frontmatter → M28 finding")
else:
    bad(f"M28 not triggered for missing frontmatter :: {m28}")


# 24. YAML frontmatter missing required fields → M28 findings
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-tasks\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
messages = m28_messages(data)
if "orderspec.status" in messages and "orderspec.slug" in messages:
    ok("missing required fields → M28 findings")
else:
    bad(f"M28 did not flag missing status/slug :: {m28_findings(data)}")


# 25. YAML frontmatter with empty required field → M28 finding
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-tasks\n"
    "  slug: tasks-001\n"
    "  status: ''\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
if any("orderspec.status" in f["message"] for f in m28_findings(data)):
    ok("empty required field → M28 finding")
else:
    bad(f"M28 did not flag empty status :: {m28_findings(data)}")


# 26. YAML frontmatter with no orderspec block → M28 findings for all required spec fields
reset_feature()
write_spec_content(
    "---\n"
    "title: My Spec\n"
    "author: someone\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
flagged_fields = m28_flagged_fields(data)
expected_fields = {
    "orderspec.artifact",
    "orderspec.feature_id",
    "orderspec.slug",
    "orderspec.status",
}
if flagged_fields == expected_fields:
    ok("frontmatter without orderspec block → M28 findings for all required spec fields")
else:
    bad(
        f"M28 did not flag all required fields :: "
        f"{m28_findings(data)} :: flagged={flagged_fields}"
    )


# 27. YAML frontmatter with quotes around values → parsed correctly
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: \"spec\"\n"
    "  feature_id: \"FEAT-001-tasks\"\n"
    "  slug: 'tasks-001'\n"
    "  status: 'draft'\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
m28 = m28_findings(data)
if not m28:
    ok("quoted YAML values → parsed correctly, no M28")
else:
    bad(f"M28 false positive on quoted values :: {m28}")


# 28. YAML frontmatter with invalid artifact → M28 finding
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: plan\n"
    "  feature_id: FEAT-001-tasks\n"
    "  slug: tasks-001\n"
    "  status: draft\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
m28 = m28_findings(data)
if any("orderspec.artifact must be 'spec'" in f["message"] for f in m28):
    ok("invalid artifact → M28 finding")
else:
    bad(f"M28 did not flag invalid artifact :: {m28}")


# 29. YAML frontmatter with invalid status → M28 finding
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-tasks\n"
    "  slug: tasks-001\n"
    "  status: in_progress\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
m28 = m28_findings(data)
if any("orderspec.status must be one of" in f["message"] for f in m28):
    ok("invalid status → M28 finding")
else:
    bad(f"M28 did not flag invalid status :: {m28}")


# 30. YAML frontmatter with unresolved placeholder → M28 finding
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: FEAT-001-tasks\n"
    "  slug: __FEATURE_SLUG__\n"
    "  status: draft\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
m28 = m28_findings(data)
if any("orderspec.slug" in f["message"] for f in m28):
    ok("unresolved placeholder in frontmatter → M28 finding")
else:
    bad(f"M28 did not flag unresolved placeholder :: {m28}")



# 31. YAML frontmatter with invalid feature_id namespace → M28 finding
reset_feature()
write_spec_content(
    "---\n"
    "orderspec:\n"
    "  artifact: spec\n"
    "  feature_id: TASKS-001\n"
    "  slug: tasks-001\n"
    "  status: draft\n"
    "---\n"
    "# Test Spec\n"
    "\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do A.\n"
)
rc, data, err = run_validate_spec_json()
m28 = m28_findings(data)
if any("orderspec.feature_id must match FEAT-NNN-slug" in f["message"] for f in m28):
    ok("invalid feature_id namespace → M28 finding")
else:
    bad(f"M28 did not flag invalid feature_id namespace :: {m28}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)