"""Regression checks for bootstrap skill discovery and installation policy."""

import unittest
from pathlib import Path


PROMPT_PATH = Path(".orderspec/framework/prompts/order.bootstrap.md")
PROTOCOL_PATH = Path(".orderspec/framework/protocols/tooling-protocol.md")


class TestOrderBootstrapTooling(unittest.TestCase):
    def setUp(self):
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.protocol = PROTOCOL_PATH.read_text(encoding="utf-8")

    def test_init_requires_discovery_for_uncovered_groups(self):
        self.assertIn(
            "On Init, discovery is required for every uncovered coverage group",
            self.prompt,
        )
        self.assertIn("Bootstrap coverage", self.protocol)

    def test_candidates_include_popularity_but_not_as_trust(self):
        self.assertIn("up to three materially distinct candidates", self.prompt)
        self.assertIn("install count", self.prompt)
        self.assertIn("Popularity is a ranking", self.prompt)
        self.assertIn("Popularity MUST NOT", self.protocol)

    def test_selection_is_exact_and_bounded(self):
        self.assertIn("one bounded selection question", self.prompt)
        for value in (
            "exact skill",
            "source",
            "refs",
            "commands",
            "canonical project-local destination",
            "enabled-agent exposure",
        ):
            self.assertIn(value, self.prompt)

    def test_project_skills_are_canonical_for_agents(self):
        self.assertIn(
            "Never install\n"
            "the same skill separately into agent-specific directories",
            self.prompt,
        )
        self.assertIn("single source of truth", self.protocol)
        self.assertIn("agents_sync.py sync --agents", self.prompt)


if __name__ == "__main__":
    unittest.main()
