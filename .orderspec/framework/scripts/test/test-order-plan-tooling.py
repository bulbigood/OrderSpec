"""test-order-plan-tooling.py — verify tooling delegation in order.plan.md"""

import unittest
from pathlib import Path

PROMPT_PATH = Path(".orderspec/framework/prompts/order.plan.md")
PROTOCOL_PATH = Path(".orderspec/framework/protocols/tooling-protocol.md")


class TestOrderPlanTooling(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PROMPT_PATH.exists(), f"{PROMPT_PATH} not found")
        self.assertTrue(PROTOCOL_PATH.exists(), f"{PROTOCOL_PATH} not found")
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.protocol = PROTOCOL_PATH.read_text(encoding="utf-8")

    def test_prompt_delegates_to_global_rules(self):
        """Prompt must delegate tooling validation via validate_tooling.py."""
        self.assertIn(
            'validate_tooling.py -C "$PWD" --json',
            self.prompt,
        )

    def test_prompt_does_not_duplicate_skill_table(self):
        """Prompt must not duplicate the skill interpretation table from tooling protocol."""
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

    def test_tooling_protocol_contains_skill_table(self):
        """Tooling protocol must contain the skill interpretation table."""
        self.assertIn(
            "installed_and_verified",
            self.protocol,
        )
        self.assertIn(
            "installed_but_missing",
            self.protocol,
        )
        self.assertIn(
            "MUST NOT silently continue",
            self.protocol,
        )

    def test_tooling_protocol_contains_matching_procedure(self):
        """Tooling protocol must contain project-contract matching."""
        self.assertIn("STACK-NNN", self.protocol)
        self.assertIn("ARCH-NNN", self.protocol)
        self.assertIn("CONV-NNN", self.protocol)
        self.assertIn("contract_refs", self.protocol)
        self.assertIn("skills.bindings", self.protocol)

    def test_tooling_protocol_forbids_hardcoded_tools(self):
        """Tooling protocol must forbid hardcoded runtime tool names."""
        self.assertIn("MUST NOT hardcode tool names", self.protocol)

    def test_done_when_includes_tooling(self):
        """Done When must still include tooling validation items."""
        self.assertIn(
            "validate_tooling.py",
            self.prompt,
        )


if __name__ == "__main__":
    unittest.main()
