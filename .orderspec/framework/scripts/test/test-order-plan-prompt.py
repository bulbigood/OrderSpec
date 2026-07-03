import unittest
import os

class TestOrderPlanPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt_path = ".orderspec/framework/prompts/order.plan.md"
        self.assertTrue(os.path.exists(self.prompt_path), f"{self.prompt_path} not found")

    def test_context_bootstrap_present(self):
        with open(self.prompt_path, "r") as f:
            content = f.read()
        self.assertIn("command_context.py resolve order.plan", content)
        self.assertIn("Command Context Resolution", content)

    def test_hooks_removed(self):
        with open(self.prompt_path, "r") as f:
            content = f.read()
        self.assertNotIn("hooks-protocol.md", content)
        self.assertNotIn("before_plan", content)
        self.assertNotIn("after_plan", content)

    def test_setup_py_restored(self):
        with open(self.prompt_path, "r") as f:
            content = f.read()
        self.assertIn("setup.py plan", content)
        self.assertIn("setup.py paths", content)

    def test_upstream_gate_restored(self):
        with open(self.prompt_path, "r") as f:
            content = f.read()
        self.assertIn("upstream_gate.py", content)

    def test_traceability_args_updated(self):
        with open(self.prompt_path, "r") as f:
            content = f.read()
        self.assertIn("-C \"$PWD\" --feature-dir \"$FEATURE_DIR\"", content)
        self.assertNotIn("init \"$FEATURE\"", content)

if __name__ == '__main__':
    unittest.main()
