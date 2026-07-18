#!/usr/bin/env python3
"""Regression tests for read-only gate target resolution."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "gate_target.py"
SETUP = Path(__file__).resolve().parent.parent / "setup.py"


class GateTargetTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="orderspec-gate-target-"))
        (self.work / ".orderspec/state").mkdir(parents=True)
        (self.work / ".orderspec/framework/templates").mkdir(parents=True)
        (self.work / ".orderspec/framework/templates/report-template.md").write_text("REPORT\n")
        self.active = self.make_feature("001-active", "FEAT-001-active")
        self.other = self.make_feature("002-other", "FEAT-002-other")
        self.state_path = self.work / ".orderspec/state/active-feature.json"
        self.state_path.write_text(json.dumps({
            "version": 1,
            "active": True,
            "feature_id": "FEAT-001-active",
            "feature_directory": ".orderspec/features/001-active",
            "spec_file": ".orderspec/features/001-active/spec.md",
            "plan_file": None,
            "tasks_file": None,
            "status": "specified",
            "last_command": "order.spec",
            "updated_at": "2026-07-18T00:00:00Z",
        }) + "\n", encoding="utf-8")
        self.original_state = self.state_path.read_text(encoding="utf-8")
        self.env = os.environ.copy()
        self.env["ORDERSPEC_ROOT"] = str(self.work)

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def make_feature(self, dirname, feature_id):
        path = self.work / ".orderspec/features" / dirname
        path.mkdir(parents=True)
        path.joinpath("spec.md").write_text(
            f"---\norderspec:\n  feature_id: {feature_id}\n---\n", encoding="utf-8"
        )
        return path

    def run_target(self, command, arguments=""):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--command", command, "--arguments", arguments, "--json"],
            cwd=self.work, env=self.env, capture_output=True, text=True,
        )

    def test_unflagged_feature_reference_is_semantic_and_does_not_switch(self):
        result = self.run_target("order.spec-check", "FEAT-002-other")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["feature_directory"], ".orderspec/features/001-active")
        self.assertEqual(data["semantic_input"], "FEAT-002-other")
        self.assertFalse(data["explicit"])
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), self.original_state)

    def test_setup_writes_only_to_active_target(self):
        target = self.run_target("order.spec-check", "authorization focus")
        feature_dir = json.loads(target.stdout)["feature_directory"]
        result = subprocess.run(
            [sys.executable, str(SETUP), "spec-check", "--feature-dir", feature_dir,
             "--refresh-template", "--json"],
            cwd=self.work, env=self.env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.active / "spec-report.md").is_file())
        self.assertFalse((self.other / "spec-report.md").exists())
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), self.original_state)

    def test_code_check_parses_base_separately(self):
        result = self.run_target("order.code-check", "focus authorization --base origin/main")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["base_ref"], "origin/main")
        self.assertEqual(data["semantic_input"], "focus authorization")

    def test_plan_check_accepts_semantic_guidance(self):
        result = self.run_target("order.plan-check", "focus authorization")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["semantic_input"], "focus authorization")

    def test_gate_rejects_unsupported_feature_control(self):
        result = self.run_target("order.spec-check", "--feature FEAT-002-other")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["error"], "unsupported_arguments")


if __name__ == "__main__":
    unittest.main()
