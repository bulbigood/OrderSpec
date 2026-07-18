#!/usr/bin/env python3
"""Regression tests for deterministic code-report validation."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from validate_code_report import finalize, finding_id, validate


def report(verdict="PASS", terminal="false", finding_row=None, routing="(none)", severity_counts="CRITICAL=0 · HIGH=0 · MEDIUM=0 · LOW=0"):
    row = finding_row or "| (none) | — | — | — | — | — | — | — |"
    return f"""---
orderspec:
  artifact: gate_report
  command: order.code-check
  model: test-model
  generated_at: 2026-07-18T12:00:00Z
  verdict: {verdict}
  assurance: STATIC_STRONG
  terminal_precondition: {terminal}
  feature_id: FEAT-001-test
  feature_directory: specs/001-test
---

## Code Check (implementation — code ↔ contract)
**Verdict**: {verdict}
**Assurance**: STATIC_STRONG
### Assurance Limits
(none)
### Routing Required
{routing}
### Findings
| ID | Source | Severity | Result | Disposition | Owner | Location ↔ Obligation | Evidence |
|----|--------|----------|--------|-------------|-------|-----------------------|----------|
{row}
### Coverage Exceptions
(none)
### Evidence Execution
(none)
### Metrics
- Findings by severity: {severity_counts}
- Report file: specs/001-test/code-report.md
"""


class CodeReportValidatorTests(unittest.TestCase):
    def validate_text(self, text):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "code-report.md"
            path.write_text(text, encoding="utf-8")
            return validate(path)

    def test_pass_without_routed_findings(self):
        result = self.validate_text(report())
        self.assertTrue(result["ok"], result["errors"])

    def test_routed_high_requires_block(self):
        fid = finding_id("C1", "order.code", "AC-001", "src/a.ts:handler")
        row = f"| {fid} | semantic | HIGH | UNPROVEN | Route | /order.code | src/a.ts:handler ↔ AC-001 | missing |"
        result = self.validate_text(report(
            verdict="ROUTING_REQUIRED",
            finding_row=row,
            routing=f"- {fid}: `/order.code`",
            severity_counts="CRITICAL=0 · HIGH=1 · MEDIUM=0 · LOW=0",
        ))
        self.assertFalse(result["ok"])
        self.assertTrue(any("deterministic verdict BLOCK" in e["message"] for e in result["errors"]))

    def test_terminal_precondition_requires_block(self):
        result = self.validate_text(report(verdict="PASS", terminal="true"))
        self.assertFalse(result["ok"])
        self.assertTrue(any("deterministic verdict BLOCK" in e["message"] for e in result["errors"]))

    def test_finding_id_is_stable_and_location_sensitive(self):
        first = finding_id("C3", "order.code", "INV-001", "src/a.ts:write")
        self.assertEqual(first, finding_id("C3", "order.code", "INV-001", "src/a.ts:write"))
        self.assertNotEqual(first, finding_id("C3", "order.code", "INV-001", "src/b.ts:write"))
        self.assertRegex(first, r"^C3-[0-9a-f]{8}$")

    def test_escaped_markdown_pipe_does_not_split_finding_row(self):
        fid = finding_id("C2", "order.code", "IF-001", "src/a.ts:handler")
        row = f"| {fid} | semantic | MEDIUM | VIOLATED | Advisory | — | src/a.ts:handler ↔ IF-001 | expected a\\|b |"
        result = self.validate_text(report(
            finding_row=row,
            severity_counts="CRITICAL=0 · HIGH=0 · MEDIUM=1 · LOW=0",
        ))
        self.assertTrue(result["ok"], result["errors"])

    def test_finalize_derives_verified_status_from_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "code-report.md"
            path.write_text(report(), encoding="utf-8")
            completed = type("Completed", (), {"returncode": 0, "stdout": '{"ok": true}', "stderr": ""})()
            with patch("validate_code_report.subprocess.run", return_value=completed) as run:
                result, rc = finalize(path)
            self.assertEqual(rc, 0)
            self.assertEqual(result["active_feature_status"], "verified")
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--status") + 1], "verified")

    def test_ledger_requires_complete_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "code-report.md"
            path.write_text(report(), encoding="utf-8")
            ledger = root / "code-obligations.json"
            ledger.write_text('{"obligation_ids":["AC-001"]}', encoding="utf-8")
            (root / "code-obligation-results.json").write_text(
                '{"ledger_ids":["AC-001"],"results":{}}', encoding="utf-8"
            )
            result = validate(path, ledger)
            self.assertFalse(result["ok"])
            self.assertTrue(any(e["field"] == "ledger.completeness" for e in result["errors"]))

    def test_not_checked_forces_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fid = finding_id("C0", "order.code", "AC-001", "src/a.ts:handler")
            row = f"| {fid} | semantic | LOW | NOT_CHECKED | Route | /order.code | src/a.ts:handler ↔ AC-001 | inspection limit |"
            text = report(
                verdict="PASS",
                finding_row=row,
                routing=f"- {fid}: `/order.code`",
                severity_counts="CRITICAL=0 · HIGH=0 · MEDIUM=0 · LOW=1",
            ).replace(
                "### Metrics\n",
                "### Metrics\n- Obligations assessed: 1\n"
                "- Results: SATISFIED=0 · VIOLATED=0 · UNPROVEN=0 · NOT_CHECKED=1\n",
            )
            path = root / "code-report.md"
            path.write_text(text, encoding="utf-8")
            ledger = root / "code-obligations.json"
            ledger.write_text('{"obligation_ids":["AC-001"]}', encoding="utf-8")
            (root / "code-obligation-results.json").write_text(json.dumps({
                "ledger_ids": ["AC-001"],
                "results": {
                    "AC-001": {
                        "obligation": "AC-001",
                        "result": "NOT_CHECKED",
                        "evidence": [],
                        "implementation_paths": [],
                        "finding": None,
                    }
                },
            }), encoding="utf-8")
            result = validate(path, ledger)
            self.assertFalse(result["ok"])
            self.assertTrue(any("deterministic verdict BLOCK" in e["message"] for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
