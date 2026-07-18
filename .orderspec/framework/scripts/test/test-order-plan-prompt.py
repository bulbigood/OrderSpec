import unittest
import os

class TestOrderPlanPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt_path = ".orderspec/framework/prompts/order.plan.md"
        self.check_prompt_path = ".orderspec/framework/prompts/order.plan-check.md"
        self.template_path = ".orderspec/framework/templates/plan-template.md"
        self.assertTrue(os.path.exists(self.prompt_path), f"{self.prompt_path} not found")
        self.assertTrue(os.path.exists(self.check_prompt_path), f"{self.check_prompt_path} not found")
        self.assertTrue(os.path.exists(self.template_path), f"{self.template_path} not found")

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

    def test_mechanism_runtime_closure_contract(self):
        with open(self.prompt_path, "r") as f:
            plan_prompt = f.read()
        with open(self.check_prompt_path, "r") as f:
            check_prompt = f.read()
        with open(self.template_path, "r") as f:
            template = f.read()

        for content in (plan_prompt, check_prompt, template):
            self.assertIn("Mechanism Evidence & Runtime Closure", content)
            self.assertIn("operational scope", content.lower())
        self.assertIn("Library/API documentation alone is insufficient runtime evidence", plan_prompt)
        self.assertIn("PLAN_BLOCKED: runtime prerequisite unverified", plan_prompt)
        self.assertIn("P1-013 Mechanism Evidence & Runtime Closure", check_prompt)
        self.assertIn("process-local lock cannot satisfy a cluster-wide", check_prompt)
        self.assertIn("Existing Project Mechanism / Reuse Decision", template)

    def test_work_order_baseline_and_cross_boundary_contract(self):
        with open(self.prompt_path, "r") as f:
            plan_prompt = f.read()
        with open(self.check_prompt_path, "r") as f:
            check_prompt = f.read()

        self.assertIn("PLAN_STOPPED: implementation baseline is active", plan_prompt)
        self.assertIn("Never absorb", plan_prompt)
        self.assertIn("Cross-boundary completeness", plan_prompt)
        self.assertIn("P1-014 Cross-Boundary Completeness", check_prompt)

    def test_plan_check_severity_model(self):
        with open(self.check_prompt_path, "r") as f:
            check_prompt = f.read()

        self.assertIn("Severity measures defect impact", check_prompt)
        self.assertIn("P0-000 (MEDIUM): no active feature", check_prompt)
        self.assertIn("P0-002 (LOW): suspected script-pattern bug", check_prompt)
        self.assertIn("| BLOCK | any routed CRITICAL/HIGH", check_prompt)
        self.assertNotIn("CRITICAL if MVP/P1", check_prompt)

if __name__ == '__main__':
    unittest.main()
