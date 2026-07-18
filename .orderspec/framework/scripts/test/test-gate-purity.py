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
    FRAMEWORK_DIR / "templates" / "code-report-template.md",
    FRAMEWORK_DIR / "scripts" / "bootstrap_contracts.py",
    FRAMEWORK_DIR / "docs" / "architecture.md",
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

    def test_plan_check_does_not_run_mutating_traceability_setup(self):
        content = (FRAMEWORK_DIR / "prompts" / "order.plan-check.md").read_text(encoding="utf-8")
        self.assertNotIn("traceability.py -C \"$PWD\" --feature-dir \"$FEATURE_DIR\" init", content)
        self.assertNotIn("traceability.py -C \"$PWD\" --feature-dir \"$FEATURE_DIR\" extract-spec-ids", content)

    def test_report_template_row_placeholders_are_not_double_wrapped(self):
        content = (FRAMEWORK_DIR / "templates" / "report-template.md").read_text(encoding="utf-8")
        for placeholder in (
            "deferred_rows",
            "findings_rows",
            "coverage_taxonomy_rows",
            "contradiction_grid_rows",
            "journey_matrix_rows",
            "if_matrix_rows",
        ):
            self.assertNotIn(f"| {{{placeholder}}} |", content)


if __name__ == "__main__":
    unittest.main()
