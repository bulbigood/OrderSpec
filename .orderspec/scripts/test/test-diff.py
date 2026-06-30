#!/usr/bin/env python3
"""test-diff.py — regression for diff engine"""

import json
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
LOG_TO_FILE = False

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test-diff.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-"))
SPECS_ROOT = WORK / "specs"
SPECS_ROOT.mkdir(parents=True, exist_ok=True)

F = "F"
SPECS = SPECS_ROOT / F
SDIR = SPECS / ".orderspec-state"
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

def write_spec(content):
    (SPECS / "spec.md").write_text(content, encoding="utf-8")

# ── git helpers ──────────────────────────────────────────────────────────────

def git_init_repo():
    subprocess.run(["git", "init"], capture_output=True, cwd=str(WORK))
    subprocess.run(["git", "config", "user.email", "test@test.com"], capture_output=True, cwd=str(WORK))
    subprocess.run(["git", "config", "user.name", "Test"], capture_output=True, cwd=str(WORK))

def git_commit(msg="snapshot"):
    subprocess.run(["git", "add", "-A"], capture_output=True, cwd=str(WORK))
    subprocess.run(["git", "commit", "-m", msg], capture_output=True, cwd=str(WORK))

def git_get_hash(ref="HEAD"):
    result = subprocess.run(
        ["git", "rev-parse", ref],
        capture_output=True, text=True, cwd=str(WORK)
    )
    return result.stdout.strip()

# ── Tests ────────────────────────────────────────────────────────────────────

# 1. diff-summary detects added IDs
reset_feature()
git_init_repo()
write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do thing A.\n"
)
git_commit("initial")
old_hash = git_get_hash()

write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "## 4. Functional Requirements\n"
    "- **REQ-001**: System MUST do thing A.\n"
    "- **REQ-002**: System MUST do thing B.\n"
)

rc, out, err = run_trace("diff-summary", "--old", old_hash, "--json", F)
try:
    data = json.loads(out)
    if rc == 0 and len(data["added"]) == 1 and data["added"][0]["id"] == "REQ-002":
        ok("diff-summary detects added IDs")
    else:
        bad(f"diff-summary added detection wrong :: rc={rc} data={data}")
except Exception as exc:
    bad(f"diff-summary output invalid :: {exc} :: {out!r}")

# 2. diff-summary detects removed IDs
reset_feature()
git_init_repo()
write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System MUST do A.\n"
    "- **REQ-002**: System MUST do B.\n"
)
git_commit("initial")
old_hash = git_get_hash()

write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System MUST do A.\n"
)

rc, out, err = run_trace("diff-summary", "--old", old_hash, "--json", F)
try:
    data = json.loads(out)
    if rc == 0 and len(data["removed"]) == 1 and data["removed"][0]["id"] == "REQ-002":
        ok("diff-summary detects removed IDs")
    else:
        bad(f"diff-summary removed detection wrong :: rc={rc} data={data}")
except Exception as exc:
    bad(f"diff-summary output invalid :: {exc} :: {out!r}")

# 3. diff-summary detects MUST → SHOULD weakening
reset_feature()
git_init_repo()
write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System MUST enforce audit consistency.\n"
)
git_commit("initial")
old_hash = git_get_hash()

write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System SHOULD enforce audit consistency.\n"
)

rc, out, err = run_trace("diff-summary", "--old", old_hash, "--json", F)
try:
    data = json.loads(out)
    if (
        rc == 0
        and len(data["changed"]) == 1
        and "weakened" in " ".join(data["changed"][0]["details"])
        and data["requires_approval"] == True
    ):
        ok("diff-summary detects MUST → SHOULD weakening")
    else:
        bad(f"diff-summary weakening detection wrong :: rc={rc} data={data}")
except Exception as exc:
    bad(f"diff-summary output invalid :: {exc} :: {out!r}")

# 4. diff-summary detects SHOULD → MUST strengthening
reset_feature()
git_init_repo()
write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System SHOULD enforce audit consistency.\n"
)
git_commit("initial")
old_hash = git_get_hash()

write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System MUST enforce audit consistency.\n"
)

rc, out, err = run_trace("diff-summary", "--old", old_hash, "--json", F)
try:
    data = json.loads(out)
    if (
        rc == 0
        and len(data["changed"]) == 1
        and "strengthened" in " ".join(data["changed"][0]["details"])
    ):
        ok("diff-summary detects SHOULD → MUST strengthening")
    else:
        bad(f"diff-summary strengthening detection wrong :: rc={rc} data={data}")
except Exception as exc:
    bad(f"diff-summary output invalid :: {exc} :: {out!r}")

# 5. diff-summary markdown output is valid
reset_feature()
git_init_repo()
write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System MUST do A.\n"
)
git_commit("initial")
old_hash = git_get_hash()

write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System MUST do A.\n"
    "- **REQ-002**: System MUST do B.\n"
)

rc, out, err = run_trace("diff-summary", "--old", old_hash, F)
if rc == 0 and "## Contract Change Summary" in out and "REQ-002" in out:
    ok("diff-summary markdown output valid")
else:
    bad(f"diff-summary markdown output wrong :: rc={rc} out={out!r}")

# 6. diff-summary with no changes reports empty
reset_feature()
git_init_repo()
write_spec(
    "---\n"
    "orderspec:\n"
    "  feature_id: TEST-001\n"
    "  status: draft\n"
    "  stack_ref: stack.md\n"
    "---\n"
    "- **REQ-001**: System MUST do A.\n"
)
git_commit("initial")
old_hash = git_get_hash()

# No changes
rc, out, err = run_trace("diff-summary", "--old", old_hash, "--json", F)
try:
    data = json.loads(out)
    if (
        rc == 0
        and len(data["added"]) == 0
        and len(data["removed"]) == 0
        and len(data["changed"]) == 0
        and data["requires_approval"] == False
    ):
        ok("diff-summary with no changes reports empty")
    else:
        bad(f"diff-summary no-change detection wrong :: rc={rc} data={data}")
except Exception as exc:
    bad(f"diff-summary output invalid :: {exc} :: {out!r}")

# ── Cleanup ──────────────────────────────────────────────────────────────────

if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)

print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
if LOG_TO_FILE:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{pass_count} passed, {fail_count} failed\n")

sys.exit(0 if fail_count == 0 else 1)