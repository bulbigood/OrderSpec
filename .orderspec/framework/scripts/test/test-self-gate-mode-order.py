#!/usr/bin/env python3
"""Prompt contracts: blocking self-gates must select Refine before Refresh."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SelfGateModeOrderTests(unittest.TestCase):
    def test_plan_and_tasks_read_self_gate_before_refresh(self):
        for command, report in (("plan", "plan-report.md"), ("tasks", "tasks-report.md")):
            content = (ROOT / "prompts" / f"order.{command}.md").read_text(encoding="utf-8")
            self.assertLess(content.index(f'SELF_REPORT="$FEATURE_DIR/{report}"'), content.index("**Refresh**"))
            self.assertIn("A blocking self-gate selects Refine even when `$ARGUMENTS` is empty.", content)

    def test_spec_selects_mode_after_self_gate_intake(self):
        content = (ROOT / "prompts" / "order.spec.md").read_text(encoding="utf-8")
        self.assertLess(content.index("## Self Gate Report Intake"), content.index("### Mode selection"))
        self.assertIn("select **Refine** even when `$ARGUMENTS` is empty", content)

    def test_all_report_readers_treat_consumed_as_inactive(self):
        for command in ("spec", "code-to-spec", "plan", "tasks", "code", "code-check"):
            content = (ROOT / "prompts" / f"order.{command}.md").read_text(encoding="utf-8")
            self.assertIn("CONSUMED_STALE", content, command)

    def test_all_marker_calls_identify_consumer_and_recheck(self):
        expected = {
            "spec": ("/order.spec", "/order.spec-check"),
            "code-to-spec": ("/order.code-to-spec", "/order.spec-check"),
            "plan": ("/order.plan", "/order.plan-check"),
            "tasks": ("/order.tasks", "/order.tasks-check"),
            "code": ("/order.code", "/order.tasks-check"),
        }
        for command, (consumer, recheck) in expected.items():
            content = (ROOT / "prompts" / f"order.{command}.md").read_text(encoding="utf-8")
            self.assertIn(f"--consumer {consumer}", content, command)
            self.assertIn(f"--recheck {recheck}", content, command)


if __name__ == "__main__":
    unittest.main()
