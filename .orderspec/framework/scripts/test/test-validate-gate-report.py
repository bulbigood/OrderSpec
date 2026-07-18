#!/usr/bin/env python3
"""Regression tests for deterministic generic gate-report finalization."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent / "validate_gate_report.py"


def report_text(*, verdict="BLOCK", mechanical_location="spec.md:4"):
    return f"""---
orderspec:
  artifact: gate_report
  command: "order.spec-check"
  verdict: "{verdict}"
---

## Spec Check

**Verdict**: {verdict}

### Findings
| ID | Source | Severity | Disposition | Location | Summary |
|----|--------|----------|-------------|----------|---------|
| M40 | mechanical | HIGH | Route | {mechanical_location} | missing provenance |
| S1-007 | semantic | MEDIUM | Route | REQ-001 | not observable |
| S0-004 | operational | LOW | Informational | validator | advisory |

### Metrics
- Findings by severity: CRITICAL=0 · HIGH=1 · MEDIUM=1 · LOW=1
"""


class ValidateGateReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orderspec-report-")
        self.root = Path(self.temp.name)
        self.report = self.root / "spec-report.md"
        self.mechanical = self.root / "mechanical.json"
        self.mechanical.write_text(json.dumps({
            "summary": {"exit_code": 1},
            "findings": [{
                "check": "M40",
                "severity": "HIGH",
                "disposition": "Route",
                "location": "spec.md:4",
                "message": "missing provenance",
            }],
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_validator(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.report),
             "--mechanical", str(self.mechanical), "--json"],
            capture_output=True, text=True,
        )

    def test_accepts_lossless_report_with_semantic_and_operational_findings(self):
        self.report.write_text(report_text(), encoding="utf-8")
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_rejects_altered_mechanical_finding(self):
        self.report.write_text(
            report_text(mechanical_location="spec.md:99"), encoding="utf-8"
        )
        result = self.run_validator()
        self.assertEqual(result.returncode, 2)
        self.assertIn("mechanical finding missing or altered", result.stdout)

    def test_rejects_inconsistent_verdict(self):
        self.report.write_text(report_text(verdict="PASS"), encoding="utf-8")
        result = self.run_validator()
        self.assertEqual(result.returncode, 2)
        self.assertIn("computed verdict is BLOCK", result.stdout)


if __name__ == "__main__":
    unittest.main()
