#!/usr/bin/env python3
"""Regression tests for the setup.py tasks-check subcommand."""

import json
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import setup


def test_tasks_check_constants_exist():
    """Test that report template constants are defined."""
    assert hasattr(setup, "REPORT_TEMPLATE_NAME")
    assert hasattr(setup, "REPORT_TEMPLATE_FILE")
    assert setup.REPORT_TEMPLATE_NAME == "report-template"
    assert setup.REPORT_TEMPLATE_FILE == "report-template.md"
    print("PASS: Constants defined correctly")


def test_tasks_check_subparser_registered():
    """Test that tasks-check subparser is registered."""
    result = subprocess.run(
        [sys.executable, ".orderspec/framework/scripts/setup.py", "--help"],
        capture_output=True, text=True, cwd=os.getcwd()
    )
    assert "tasks-check" in result.stdout, f"tasks-check not found in help output"
    print("PASS: tasks-check subparser registered")


def test_tasks_check_function_exists():
    """Test that cmd_tasks_check function exists."""
    assert hasattr(setup, "cmd_tasks_check")
    assert callable(setup.cmd_tasks_check)
    print("PASS: cmd_tasks_check function exists")


def test_tasks_check_reports_without_tasks():
    """Test that tasks-check creates a report when tasks.md is missing."""
    WORK = Path(tempfile.mkdtemp(prefix="orderspec-tc-test-"))
    try:
        (WORK / ".orderspec" / "framework" / "templates").mkdir(parents=True, exist_ok=True)
        (WORK / ".orderspec" / "state").mkdir(parents=True, exist_ok=True)
        (WORK / ".orderspec" / "framework" / "templates" / "report-template.md").write_text("TEMPLATE\n")

        fdir = WORK / "specs" / "F"
        fdir.mkdir(parents=True, exist_ok=True)
        (fdir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (fdir / "plan.md").write_text("# Plan\n", encoding="utf-8")

        (WORK / ".orderspec" / "state" / "active-feature.json").write_text(
            json.dumps({"feature_directory": "specs/F", "spec_file": "specs/F/spec.md", "status": "draft"}) + "\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["ORDERSPEC_ROOT"] = str(WORK)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "setup.py"), "tasks-check", "--json"],
            capture_output=True, text=True, env=env, cwd=str(WORK),
        )
        assert result.returncode == 0, f"Expected rc=0, got {result.returncode}: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["TASKS_EXISTS"] is False
        assert (fdir / "tasks-report.md").is_file()
        print("PASS: tasks-check reports without tasks.md")
    finally:
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    try:
        test_tasks_check_constants_exist()
        test_tasks_check_function_exists()
        test_tasks_check_subparser_registered()
        test_tasks_check_reports_without_tasks()
        print("\nAll tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTest failed: {e}", file=sys.stderr)
        sys.exit(1)
