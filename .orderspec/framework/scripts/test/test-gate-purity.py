#!/usr/bin/env python3
"""Regression checks for inspector-only gate surfaces."""

import unittest
from pathlib import Path


ORDERSPEC_DIR = Path(__file__).resolve().parents[3]
FRAMEWORK_DIR = ORDERSPEC_DIR / "framework"

CHECK_SURFACES = [
    FRAMEWORK_DIR / "prompts" / "order.spec-check.md",
    FRAMEWORK_DIR / "prompts" / "order.plan-check.md",
    FRAMEWORK_DIR / "prompts" / "order.tasks-check.md",
    FRAMEWORK_DIR / "prompts" / "order.code-check.md",
    FRAMEWORK_DIR / "templates" / "report-template.md",
    FRAMEWORK_DIR / "scripts" / "bootstrap_contracts.py",
    ORDERSPEC_DIR / "docs" / "architecture.md",
]

FORBIDDEN_MUTATION_TERMS = (
    "auto" + "fix",
    "auto" + "-fix",
    "auto" + "_fixed",
    "auto" + "-fixed",
    "applied " + "automatically",
)


class TestGatePurity(unittest.TestCase):
    def test_gate_surfaces_have_no_mutation_channel(self):
        for path in CHECK_SURFACES:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8").lower()
                for term in FORBIDDEN_MUTATION_TERMS:
                    self.assertNotIn(term, content)

    def test_check_prompts_declare_inspector_role(self):
        for path in CHECK_SURFACES[:4]:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8").lower()
                self.assertIn("pure inspector", content)
                self.assertIn("route", content)


if __name__ == "__main__":
    unittest.main()
