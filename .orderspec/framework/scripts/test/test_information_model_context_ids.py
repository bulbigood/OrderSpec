#!/usr/bin/env python3
"""Regression tests for stable Information Model context IDs."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from trace_validate import _check_m41_information_model_ids  # noqa: E402


def findings_for(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    def add(check: str, severity: str, location: str, message: str) -> None:
        findings.append(
            {"check": check, "severity": severity, "location": location, "message": message}
        )

    _check_m41_information_model_ids(text, add)
    return findings


valid = """### Entity ENT-001: Task
| Field | Type |
|---|---|
| id | Identifier |

### Structure STR-001: Snapshot
| Field | Type |
|---|---|
| title | String |

### Value Set VAL-001: Status
| Value | Description |
|---|---|
| open | Active |
"""
assert findings_for(valid) == []

legacy = findings_for("### Entity: Task\n")
assert len(legacy) == 1 and "requires stable context ID ENT-NNN" in legacy[0]["message"]

wrong_kind = findings_for("### Entity STR-001: Task\n")
assert len(wrong_kind) == 1 and "must use ENT-NNN" in wrong_kind[0]["message"]

duplicate = findings_for("### Entity ENT-001: Task\n### Entity ENT-001: Other\n")
assert len(duplicate) == 1 and "Duplicate Information Model ID ENT-001" in duplicate[0]["message"]

print("All Information Model context-ID tests passed")
