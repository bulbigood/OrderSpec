#!/usr/bin/env python3
"""Regression tests for OrderSpec control/semantic input separation."""

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from command_input import parse_input  # noqa: E402


class CommandInputTests(unittest.TestCase):
    def test_unflagged_text_is_semantic(self):
        result = parse_input("order.spec-check", "PLAN_BLOCKED: contract decision required")
        self.assertTrue(result["ok"])
        self.assertEqual(result["controls"], {})
        self.assertEqual(result["semantic_input"], "PLAN_BLOCKED: contract decision required")

    def test_named_control_is_separate(self):
        result = parse_input("order.code-check", "focus authorization --base origin/main")
        self.assertTrue(result["ok"])
        self.assertEqual(result["controls"], {"base": "origin/main"})
        self.assertEqual(result["semantic_input"], "focus authorization")

    def test_feature_selection_requires_named_control(self):
        semantic = parse_input("order.feature", "FEAT-002-billing")
        selected = parse_input("order.feature", "--select FEAT-002-billing")
        self.assertEqual(semantic["controls"], {})
        self.assertEqual(semantic["semantic_input"], "FEAT-002-billing")
        self.assertEqual(selected["controls"], {"select": "FEAT-002-billing"})
        self.assertEqual(selected["semantic_input"], "")

    def test_unknown_control_is_rejected(self):
        result = parse_input("order.spec-check", "--feature FEAT-002-billing")
        self.assertFalse(result["ok"])
        self.assertIn("unsupported control: --feature", result["validation_errors"])

    def test_missing_value_is_rejected(self):
        result = parse_input("order.feature", "--select")
        self.assertFalse(result["ok"])
        self.assertIn("--select requires one value", result["validation_errors"])

    def test_incompatible_controls_are_rejected(self):
        result = parse_input("order.spec", "--new --split feature text")
        self.assertFalse(result["ok"])
        self.assertIn("--new and --split are mutually exclusive", result["validation_errors"])


if __name__ == "__main__":
    unittest.main()
