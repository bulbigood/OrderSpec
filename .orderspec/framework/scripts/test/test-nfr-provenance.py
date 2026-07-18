#!/usr/bin/env python3
"""Unit tests for durable MUST-level NFR provenance."""

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from trace_validate import _check_m40_nfr_provenance  # noqa: E402


def findings_for(text):
    findings = []

    def add(check, severity, location, message):
        findings.append((check, severity, location, message))

    _check_m40_nfr_provenance(text, add)
    return findings


class NfrProvenanceTests(unittest.TestCase):
    def test_missing_must_source_is_blocking(self):
        findings = findings_for("- **NFR-001**: System MUST respond within 2 seconds.\n")
        self.assertEqual([(item[0], item[1]) for item in findings], [("M40", "HIGH")])

    def test_user_and_contract_sources_are_accepted(self):
        text = """- **NFR-001**: System MUST respond within 2 seconds.
  - **Source**: user-request
- **NFR-002**: System MUST retain records for 30 days.
  - **Source**: `GOV-012`
"""
        self.assertEqual(findings_for(text), [])

    def test_qualitative_should_does_not_require_source_mechanically(self):
        text = "- **NFR-001**: System SHOULD remain easy to operate.\n"
        self.assertEqual(findings_for(text), [])


if __name__ == "__main__":
    unittest.main()
