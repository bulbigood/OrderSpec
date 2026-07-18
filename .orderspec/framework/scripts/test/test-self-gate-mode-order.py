#!/usr/bin/env python3
"""Prompt contracts: blocking self-gates must select Refine before Refresh."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SelfGateModeOrderTests(unittest.TestCase):
    def test_plan_and_tasks_read_self_gate_before_refresh(self):
        for command, report, stop_marker in (
            ("plan", "plan-report.md", "If `plan.md` already exists"),
            ("tasks", "tasks-report.md", "**Existing/Stop**"),
        ):
            content = (ROOT / "prompts" / f"order.{command}.md").read_text(encoding="utf-8")
            self.assertLess(content.index(f'SELF_REPORT="$FEATURE_DIR/{report}"'), content.index(stop_marker))
            self.assertIn("selects Refine even when `input.semantic_input` is empty", content)

    def test_spec_selects_mode_after_self_gate_intake(self):
        content = (ROOT / "prompts" / "order.spec.md").read_text(encoding="utf-8")
        self.assertLess(content.index("## Self Gate Report Intake"), content.index("### Mode selection"))
        self.assertIn("select **Refine** even when `input.semantic_input` is empty", content)

    def test_spec_explicit_mode_flags_keep_precedence(self):
        content = (ROOT / "prompts" / "order.spec.md").read_text(encoding="utf-8")
        self.assertIn("`--new` always selects Create", content)
        self.assertIn("`--split` always selects Decompose", content)
        self.assertIn("never override an explicit flag", content)
        self.assertIn("do not load its\nself-report or feedback", content)

    def test_spec_uses_active_target_and_validates_every_mutation(self):
        content = (ROOT / "prompts" / "order.spec.md").read_text(encoding="utf-8")
        self.assertIn("Use only validated active state as existing target", content)
        self.assertIn("/order.feature --select <feature-ref>", content)
        self.assertNotIn("active_feature.py resolve <feature-ref>", content)
        self.assertIn("every spec mutated in this run", content)
        self.assertIn("for **each** mutated target", content)
        self.assertIn("until every mutated target passes", content)

    def test_spec_uses_one_consequential_question_per_round(self):
        content = (ROOT / "prompts" / "order.spec.md").read_text(encoding="utf-8")
        self.assertIn("Ask one question per round", content)
        self.assertNotIn("Ask at most three questions per round", content)

    def test_spec_check_covers_role_purity_as_bounded_judgment(self):
        content = (ROOT / "prompts" / "order.spec-check.md").read_text(encoding="utf-8")
        self.assertIn("### S1-014 — Role purity", content)
        self.assertIn("one bounded semantic judgment at a time", content)
        self.assertIn("label the current report untrusted", content)

    def test_all_report_readers_treat_consumed_as_inactive(self):
        for command in ("spec", "code-to-spec", "plan", "tasks", "code-check"):
            content = (ROOT / "prompts" / f"order.{command}.md").read_text(encoding="utf-8")
            self.assertIn("CONSUMED_STALE", content, command)

        code = (ROOT / "prompts" / "order.code.md").read_text(encoding="utf-8")
        self.assertIn("code_workflow.py preflight", code)
        upstream = (ROOT / "scripts" / "upstream_gate.py").read_text(encoding="utf-8")
        self.assertIn("CONSUMED_STALE", upstream)

    def test_all_marker_calls_identify_consumer_and_recheck(self):
        expected = {
            "spec": ("/order.spec", "/order.spec-check"),
            "code-to-spec": ("/order.code-to-spec", "/order.spec-check"),
            "plan": ("/order.plan", "/order.plan-check"),
            "tasks": ("/order.tasks", "/order.tasks-check"),
        }
        for command, (consumer, recheck) in expected.items():
            content = (ROOT / "prompts" / f"order.{command}.md").read_text(encoding="utf-8")
            self.assertIn(f"--consumer {consumer}", content, command)
            self.assertIn(f"--recheck {recheck}", content, command)

        code = (ROOT / "prompts" / "order.code.md").read_text(encoding="utf-8")
        self.assertIn("not consumed by `/order.code`", code)
        self.assertNotIn("--consumer /order.code", code)


if __name__ == "__main__":
    unittest.main()
