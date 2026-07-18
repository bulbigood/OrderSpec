#!/usr/bin/env python3
"""Test setup.py --shell-vars and --json output format.

Portable: Python 3 standard library only.
Creates a temporary workspace with a mock active-feature state so the test
does not depend on any real feature being configured in the repo.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SETUP = SCRIPT_DIR.parent / "setup.py"
PY = sys.executable

if not SETUP.exists():
    print(f"FATAL: setup.py not found at {SETUP}", file=sys.stderr)
    sys.exit(2)


# ── Temporary workspace setup ────────────────────────────────────────────────

WORK = Path(tempfile.mkdtemp(prefix="orderspec-shellvars-test-"))
STATE_DIR = WORK / ".orderspec" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
FEATURE_DIR = WORK / "features" / "test-feature"
FEATURE_DIR.mkdir(parents=True, exist_ok=True)
(FEATURE_DIR / "spec.md").write_text("# spec\n", encoding="utf-8")

ACTIVE_FEATURE = STATE_DIR / "active-feature.json"
ACTIVE_FEATURE.write_text(
    json.dumps({
        "feature_id": "test-feature",
        "feature_directory": str(FEATURE_DIR.resolve()),
        "spec_file": str((FEATURE_DIR / "spec.md").resolve()),
        "status": "draft",
    }) + "\n",
    encoding="utf-8",
)


def cleanup():
    shutil.rmtree(WORK, ignore_errors=True)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_shell_vars_output():
    """Test that --shell-vars produces eval-ready shell assignments."""
    cmd = [PY, str(SETUP), "paths", "--shell-vars"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(WORK),
    )

    if result.returncode != 0:
        print(f"WORK: {WORK}")
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        assert False, f"Expected exit 0, got {result.returncode}"

    assert result.stdout, "Expected non-empty stdout"

    lines = result.stdout.strip().split("\n")
    required_keys = {"REPO_ROOT", "FEATURE_ID", "FEATURE_DIR", "FEATURE_SPEC", "IMPL_PLAN"}
    found_keys = set()

    for line in lines:
        if "=" in line and line.split("=")[0] in required_keys:
            key = line.split("=")[0]
            found_keys.add(key)
            assert '"' in line, f"Expected quoted value: {line}"

    assert required_keys.issubset(found_keys), f"Missing keys: {required_keys - found_keys}"


def test_json_still_works():
    """Test that --json still works as default."""
    cmd = [PY, str(SETUP), "paths", "--json"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(WORK),
    )

    if result.returncode != 0:
        print(f"WORK: {WORK}")
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        assert False, f"Expected exit 0, got {result.returncode}"

    assert result.stdout.startswith("{"), "Expected JSON output"


if __name__ == "__main__":
    try:
        test_shell_vars_output()
        test_json_still_works()
        print("All tests passed!")
    finally:
        cleanup()
