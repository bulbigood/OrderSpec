#!/usr/bin/env python3
"""Contract tests for the order.tasks-check prompt."""

import unittest
from pathlib import Path


PROMPT = (
    Path(__file__).resolve().parents[2] / "prompts" / "order.tasks-check.md"
).read_text(encoding="utf-8")


class TasksCheckPromptTests(unittest.TestCase):
    def test_severity_is_distinct_from_terminal_block(self):
        self.assertIn("## Severity Model", PROMPT)
        self.assertIn("Severity measures defect impact", PROMPT)
        self.assertIn("T0-000 (MEDIUM): no active feature", PROMPT)
        self.assertIn("T0-005 (HIGH): upstream plan.md missing", PROMPT)
        self.assertNotIn("CRITICAL if MVP/P1", PROMPT)
        self.assertNotIn("CRITICAL if it blocks", PROMPT)

    def test_all_semantic_passes_are_reported(self):
        self.assertIn("T1-xxx through T8-xxx", PROMPT)
        self.assertIn("semantic findings (T1-T8)", PROMPT)
        self.assertIn("Assign HIGH for P1/MVP and MEDIUM otherwise", PROMPT)

    def test_verdict_covers_every_routed_high(self):
        self.assertIn("| BLOCK | any routed CRITICAL/HIGH;", PROMPT)

    def test_semantic_scope_includes_granularity_and_prerequisites(self):
        self.assertIn("T2 — executable boundaries", PROMPT)
        self.assertIn("T8 — prerequisite closure", PROMPT)
        self.assertIn("T2c", PROMPT)

    def test_plan_advisory_is_informational(self):
        self.assertIn("T0-007 (MEDIUM, Informational)", PROMPT)
        self.assertIn("recommend `/order.plan-check`", PROMPT)

    def test_delivery_strategy_is_plan_selected(self):
        self.assertIn("Plan-Selected Delivery Ordering", PROMPT)
        self.assertIn("non-migration plan MUST NOT", PROMPT)


if __name__ == "__main__":
    unittest.main()
