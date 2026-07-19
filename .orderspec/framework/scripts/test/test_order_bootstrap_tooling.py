"""Regression checks for bootstrap skill discovery and installation policy."""

import unittest
import json
from pathlib import Path


PROMPT_PATH = Path(".orderspec/framework/prompts/order.bootstrap.md")
PROTOCOL_PATH = Path(".orderspec/framework/protocols/tooling-protocol.md")
MANIFEST_PATH = Path(".orderspec/framework/command-context.json")


class TestOrderBootstrapTooling(unittest.TestCase):
    def setUp(self):
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

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

    def test_bootstrap_owns_and_manages_automation_policy(self):
        self.assertIn("`.orderspec/config/automation.json`", self.prompt)
        self.assertIn("automation_config.py init", self.prompt)
        self.assertIn("automation_config.py validate", self.prompt)
        self.assertIn("automation_config.py set-enabled", self.prompt)
        self.assertIn("automation_config.py write", self.prompt)
        self.assertIn("explicitly requests an automation change", self.prompt)
        self.assertIn("Never weaken hard operator-input", self.prompt)

    def test_bootstrap_context_receives_automation_config_and_schema(self):
        bootstrap = self.manifest["commands"]["order.bootstrap"]
        self.assertTrue(any(item.get("ref") == "config.automation" for item in bootstrap["read_if_exists"]))
        self.assertTrue(any(item.get("ref") == "schema.automation_config" for item in bootstrap["required"]))
        self.assertEqual(self.manifest["resources"]["config.automation"]["authority"], "operator_config")


if __name__ == "__main__":
    unittest.main()
