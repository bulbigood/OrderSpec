#!/usr/bin/env python3
"""Regression tests for the setup.py spec-check subcommand."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import setup


def test_spec_check_constants_exist():
    """Test that report template constants are defined."""
    assert hasattr(setup, "REPORT_TEMPLATE_NAME")
    assert hasattr(setup, "REPORT_TEMPLATE_FILE")
    assert hasattr(setup, "SPEC_REPORT_FILE")
    assert setup.REPORT_TEMPLATE_NAME == "report-template"
    assert setup.REPORT_TEMPLATE_FILE == "report-template.md"
    assert setup.SPEC_REPORT_FILE == "spec-report.md"
    print("PASS: Constants defined correctly")


def test_spec_check_subparser_registered():
    """Test that spec-check subparser is registered."""
    parser = setup.main.__wrapped__ if hasattr(setup.main, "__wrapped__") else None
    
    # Parse --help to see if spec-check is listed
    result = subprocess.run(
        [sys.executable, ".orderspec/framework/scripts/setup.py", "--help"],
        capture_output=True, text=True, cwd=os.getcwd()
    )
    assert "spec-check" in result.stdout, f"spec-check not found in help output"
    print("PASS: spec-check subparser registered")


def test_spec_check_function_exists():
    """Test that cmd_spec_check function exists."""
    assert hasattr(setup, "cmd_spec_check")
    assert callable(setup.cmd_spec_check)
    print("PASS: cmd_spec_check function exists")


if __name__ == "__main__":
    try:
        test_spec_check_constants_exist()
        test_spec_check_function_exists()
        test_spec_check_subparser_registered()
        print("\nAll tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTest failed: {e}", file=sys.stderr)
        sys.exit(1)
