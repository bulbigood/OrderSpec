"""test-order-plan-tooling.py — verify tooling-related sections in order.plan.md"""

import unittest
from pathlib import Path

PROMPT_PATH = Path(".orderspec/framework/prompts/order.plan.md")


class TestOrderPlanTooling(unittest.TestCase):
    def setUp(self):
        self.assertTrue(PROMPT_PATH.exists(), f"{PROMPT_PATH} not found")
        self.content = PROMPT_PATH.read_text(encoding="utf-8")

    def test_validate_tooling_in_availability_checks(self):
        """validate_tooling.py must be listed in Script Availability Checks."""
        self.assertIn("validate_tooling.py", self.content)
        self.assertIn(
            "deterministic tooling.json and installed skills validation",
            self.content,
        )

    def test_validate_tooling_called_in_outline(self):
        """validate_tooling.py must be called in Outline step 2."""
        self.assertIn(
            'validate_tooling.py -C "$PWD" --json',
            self.content,
        )

    def test_no_hardcoded_context7(self):
        """Context7 must not be hardcoded as a procedural instruction.

        It may appear in example configs or data references, but the prompt
        must not instruct the agent to use Context7 by name.
        """
        # The old hardcoded line should be gone
        self.assertNotIn(
            "If Context7 is available and policy is `required_if_available`, query Context7",
            self.content,
        )

    def test_tooling_protocol_deference(self):
        """Prompt must defer to tooling-protocol.md, not duplicate its rules."""
        self.assertIn(
            "You MUST follow the tooling protocol for all tooling and documentation verification decisions",
            self.content,
        )
        self.assertIn("Do not hardcode tool names", self.content)

    def test_skill_matching_procedure_present(self):
        """Skill matching procedure must reference STACK-NNN → bindings."""
        self.assertIn("STACK-NNN", self.content)
        self.assertIn("match.stack_id", self.content)
        self.assertIn("skills.bindings", self.content)

    def test_installed_but_missing_handling(self):
        """Prompt must handle installed_but_missing per tooling-protocol.md."""
        self.assertIn("installed_but_missing", self.content)
        self.assertIn("MUST NOT silently continue", self.content)

    def test_done_when_includes_tooling(self):
        """Done When must include tooling validation items."""
        self.assertIn(
            "`validate_tooling.py --json` was run",
            self.content,
        )
        self.assertIn(
            "Tooling evidence recorded in `plan.md`",
            self.content,
        )

    def test_evidence_section_reference(self):
        """Prompt must reference Library Documentation Evidence section."""
        self.assertIn("## Library Documentation Evidence", self.content)


if __name__ == "__main__":
    unittest.main()
