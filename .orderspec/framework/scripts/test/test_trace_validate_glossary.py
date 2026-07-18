#!/usr/bin/env python3
"""Regression tests for trace_validate.py glossary detection."""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trace_validate import _compute_categories

def test_glossary_at_section_3():
    """Test that Glossary is detected when it's at §3 instead of §16/§17."""
    spec_text = """# Feature Spec

## 1. Executive Summary
Some content.

## 2. Goal & Scope
Some content.

## 3. Glossary
| Term | Definition |
|------|------------|
| Soft Delete | Logical removal |

## 4. Functional Requirements
Some content.
"""
    cats = _compute_categories(spec_text)
    assert cats.get("Glossary") == "present", f"Expected 'present', got '{cats.get('Glossary')}'"
    print("PASS: Glossary at §3 detected correctly")

def test_glossary_at_section_16():
    """Test that Glossary is still detected when it's at §16."""
    spec_text = """# Feature Spec

## 4. Functional Requirements
Some content.

## 16. Glossary
| Term | Definition |
|------|------------|
| Soft Delete | Logical removal |
"""
    cats = _compute_categories(spec_text)
    assert cats.get("Glossary") == "present", f"Expected 'present', got '{cats.get('Glossary')}'"
    print("PASS: Glossary at §16 detected correctly")

def test_glossary_missing():
    """Test that Glossary is reported missing when absent."""
    spec_text = """# Feature Spec

## 4. Functional Requirements
Some content.
"""
    cats = _compute_categories(spec_text)
    assert cats.get("Glossary") == "missing", f"Expected 'missing', got '{cats.get('Glossary')}'"
    print("PASS: Missing Glossary detected correctly")

def test_glossary_with_number_in_title():
    """Test that Glossary is detected with various section numbers."""
    spec_text = """# Feature Spec

## 5. Glossary
Content here.
"""
    cats = _compute_categories(spec_text)
    assert cats.get("Glossary") == "present", f"Expected 'present', got '{cats.get('Glossary')}'"
    print("PASS: Glossary at §5 detected correctly")

if __name__ == "__main__":
    try:
        test_glossary_at_section_3()
        test_glossary_at_section_16()
        test_glossary_missing()
        test_glossary_with_number_in_title()
        print("\nAll tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTest failed: {e}", file=sys.stderr)
        sys.exit(1)
