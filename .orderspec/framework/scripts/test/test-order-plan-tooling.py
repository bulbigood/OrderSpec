"""test-order-plan-tooling.py — verify tooling delegation in order.plan.md"""

import unittest
from pathlib import Path

PROMPT_PATH = Path(".orderspec/framework/prompts/order.plan.md")
RULES_PATH = Path(".orderspec/framework/orderspec-rules.md")


class TestOrderPlanTooling(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PROMPT_PATH.exists(), f"{PROMPT_PATH} not found")
        self.assertTrue(RULES_PATH.exists(), f"{RULES_PATH} not found")
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.rules = RULES_PATH.read_text(encoding="utf-8")

    def test_prompt_delegates_to_global_rules(self):
        """Prompt must delegate to global Documentation Evidence and Tooling Policy."""
        self.assertIn(
            "Documentation Evidence and Tooling Policy",
            self.prompt,
        )
        self.assertIn(
            "orderspec-rules.md",
            self.prompt,
        )

    def test_prompt_does_not_duplicate_skill_table(self):
        """Prompt must not duplicate the skill interpretation table from global rules."""
        # This table belongs in global rules, not in the prompt
        self.assertNotIn(
            "installed_but_missing | Binding declared installed but skill files NOT found",
            self.prompt,
        )

    def test_prompt_still_calls_validate_tooling(self):
        """Prompt must still call validate_tooling.py as a procedural step."""
        self.assertIn(
            'validate_tooling.py -C "$PWD" --json',
            self.prompt,
        )

    def test_global_rules_contain_skill_table(self):
        """Global rules must contain the skill interpretation table."""
        self.assertIn(
            "installed_and_verified",
            self.rules,
        )
        self.assertIn(
            "installed_but_missing",
            self.rules,
        )
        self.assertIn(
            "MUST NOT silently continue",
            self.rules,
        )

    def test_global_rules_contain_matching_procedure(self):
        """Global rules must contain the STACK-NNN matching procedure."""
        self.assertIn("STACK-NNN", self.rules)
        self.assertIn("match.stack_id", self.rules)
        self.assertIn("skills.bindings", self.rules)

    def test_global_rules_forbid_hardcoded_tools(self):
        """Global rules must forbid hardcoding tool names."""
        self.assertIn("MUST NOT hardcode tool names", self.rules)

    def test_done_when_includes_tooling(self):
        """Done When must still include tooling validation items."""
        self.assertIn(
            "`validate_tooling.py --json` was run",
            self.prompt,
        )
        self.assertIn(
            "Tooling evidence recorded in `plan.md`",
            self.prompt,
        )


if __name__ == "__main__":
    unittest.main()
