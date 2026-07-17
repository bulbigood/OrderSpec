#!/usr/bin/env python3
"""Regression tests for semantic spec category detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trace_validate import _compute_categories, _compute_journey_matrix


def test_categories_follow_titles_not_section_numbers():
    spec_text = """# Feature Spec

## 1. Overview
Summary.

## 2. Scope
### Success Criteria
- **SC-001**: A measurable outcome.

## 3. Requirements
- **REQ-001**: System MUST provide behaviour.

## 4. Non-Functional Requirements
- **NFR-001**: System SHOULD remain understandable.

## 5. Logical Architecture and Behaviour
Logical roles.

## 6. Project Constraints
Project rules.

## 7. Information Model
Logical entity.

## 8. Invariants and Edge Cases
- **INV-001**: State MUST remain valid.
- **EDGE-001**: Boundary input.

## 9. Interface Contracts
- **IF-001**: Read resource.

## 11. User Journeys
- **UJ-001**: Owner journey.

## 12. Acceptance Criteria
- **AC-001**: Given state, when action, then outcome. [Covers: REQ-001, IF-001]

## 13. Decisions and Assumptions
- **DEC-001**: Use resolved contract.
- **ASM-001**: [default] Use ordinary default.

## 15. Open Questions
None — all requirements are resolved.

## 16. Glossary
| Term | Definition |
|------|------------|
| Task | Work item |

## 17. Changelog
| Date | Change |
|------|--------|
| 2026-01-01 | Initial |
"""

    categories = _compute_categories(spec_text)

    expected_present = {
        "Functional Requirements",
        "Non-Functional Requirements",
        "Project Constraints Applied",
        "Architecture & Behaviour",
        "Information Model",
        "Interface Contracts",
        "Invariants",
        "Edge Cases",
        "Acceptance Criteria & User Journeys",
        "Open Questions",
        "Decisions",
        "Assumptions",
        "Success Criteria",
        "Glossary",
        "Changelog",
    }
    missing = [
        name for name in expected_present
        if categories.get(name) != "present"
    ]
    assert not missing, f"Expected semantic headings to be present: {missing}; got {categories}"

    assert categories["Functional Requirements"] != "missing"
    assert categories["Non-Functional Requirements"] != "missing"


def test_id_backed_categories_do_not_report_content_as_missing():
    spec_text = """# Feature Spec

## Contract Details
- **SC-001**: A measurable outcome.
- **DEC-001**: A resolved decision.
- **ASM-001**: [default] A low-impact default.
"""

    categories = _compute_categories(spec_text)

    assert categories["Success Criteria"] == "present"
    assert categories["Decisions"] == "present"
    assert categories["Assumptions"] == "present"


def test_journey_matrix_supports_split_sections_and_table_rows():
    split_sections = """## 11. User Journeys

- **UJ-001**: Owner journey.
  | Field | Value |
  |---|---|
  | Priority | P1 — core journey |
  | Covers | REQ-001, IF-001 |

## 12. Acceptance Criteria

- **AC-001**: [Covers: REQ-001, IF-001] Given state, when action, then outcome.
"""
    matrix = _compute_journey_matrix(
        split_sections,
        {"AC-001": ["REQ-001", "IF-001"]},
    )

    assert len(matrix) == 1
    assert matrix[0]["uj_id"] == "UJ-001"
    assert matrix[0]["priority"] == "P1"
    assert matrix[0]["covers_reqs"] == ["REQ-001"]
    assert matrix[0]["acs"] == []


def test_journey_matrix_keeps_nested_acceptance_criteria_with_journey():
    same_section = """## 12. Acceptance Criteria & User Journeys

- **UJ-001**: Owner journey.
  Covers: REQ-001
  - **AC-001**: [Covers: REQ-001] Given state, when action, then outcome.
"""
    matrix = _compute_journey_matrix(
        same_section,
        {"AC-001": ["REQ-001"]},
    )

    assert matrix[0]["acs"] == ["AC-001"]
    assert matrix[0]["acs_trace_to_reqs"] is True


if __name__ == "__main__":
    test_categories_follow_titles_not_section_numbers()
    test_id_backed_categories_do_not_report_content_as_missing()
    test_journey_matrix_supports_split_sections_and_table_rows()
    test_journey_matrix_keeps_nested_acceptance_criteria_with_journey()
    print("PASS: semantic category detection")
