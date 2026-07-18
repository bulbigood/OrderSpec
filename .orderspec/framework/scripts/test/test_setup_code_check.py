#!/usr/bin/env python3
"""Regression tests for setup.py code-check."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SETUP = Path(__file__).resolve().parent.parent / "setup.py"


class CodeCheckSetupTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="orderspec-code-check-setup-"))
        (self.work / ".orderspec/framework/templates").mkdir(parents=True)
        (self.work / ".orderspec/state").mkdir(parents=True)
        (self.work / ".orderspec/framework/templates/code-report-template.md").write_text(
            "CODE REPORT TEMPLATE\n", encoding="utf-8"
        )
        self.feature = self.work / "specs/F"
        self.feature.mkdir(parents=True)
        (self.work / ".orderspec/state/active-feature.json").write_text(
            json.dumps({"feature_directory": "specs/F", "status": "implementing"}) + "\n",
            encoding="utf-8",
        )
        self.env = os.environ.copy()
        self.env["ORDERSPEC_ROOT"] = str(self.work)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def run_setup(self, *args):
        return subprocess.run(
            [sys.executable, str(SETUP), "code-check", *args],
            cwd=self.work,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def test_creates_report_even_when_spec_is_missing(self):
        result = self.run_setup("--json", "--refresh-template")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["SPEC_EXISTS"])
        self.assertFalse(data["PLAN_EXISTS"])
        self.assertFalse(data["TASKS_EXISTS"])
        self.assertEqual(
            (self.feature / "code-report.md").read_text(encoding="utf-8"),
            "CODE REPORT TEMPLATE\n",
        )

    def test_preserves_without_refresh_and_overwrites_with_refresh(self):
        report = self.feature / "code-report.md"
        report.write_text("EXISTING\n", encoding="utf-8")
        result = self.run_setup("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report.read_text(encoding="utf-8"), "EXISTING\n")
        result = self.run_setup("--json", "--refresh-template")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report.read_text(encoding="utf-8"), "CODE REPORT TEMPLATE\n")


if __name__ == "__main__":
    unittest.main()
