#!/usr/bin/env python3
"""trace_constants.py — shared constants for traceability modules."""

import re

TAB = "\t"

FEATURE_STATE_DIRNAME = ".state"

MECH_MARKER = "#orderspec mechanisms v1"
MECH_COLNAMES = f"spec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type"

TRACE_MARKER = "#orderspec traceability v1"
TRACE_COLNAMES = f"spec_id{TAB}task_ids{TAB}files{TAB}source"

SPECIDS_MARKER = "#orderspec spec-ids v1"
SPECIDS_COLNAMES = f"spec_id{TAB}kind{TAB}section"

SPEC_PREFIXES = ["REQ", "NFR", "SC", "INV", "EDGE", "UJ", "AC", "Q", "ASM", "DEC", "IF"]
REQUIRED_MECHANISM_PREFIXES = {"REQ", "NFR", "INV", "EDGE", "AC", "IF"}
FORBIDDEN_MECHANISM_PREFIXES = {"SC", "UJ", "Q", "DEC"}

SPEC_PREFIX_RE = re.compile(r"^\s*- \*\*(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})\*\*")
ID_RE = re.compile(r"\b(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})\b")
TASK_LINE_RE = re.compile(r"^- \[[ xX]\] T(\d{3})")
COVERS_RE = re.compile(r"^\s*\*{0,2}Covers?\*{0,2}\s*:", re.IGNORECASE)
AC_COVERS_RE = re.compile(r"\[Covers:\s*([^\]]+)\]", re.IGNORECASE)

SECTION_MAP = {
    "REQ": "functional",
    "NFR": "non-functional",
    "SC": "success-criteria",
    "INV": "invariants",
    "EDGE": "edge-cases",
    "UJ": "user-journeys",
    "AC": "acceptance",
    "Q": "open-questions",
    "ASM": "assumptions",
    "IF": "interface-contracts",
    "DEC": "decisions",
}

IF_REQUIRED_FIELDS = [
    ("Kind", "HIGH"),
    ("Operation", "HIGH"),
    ("Actor", "HIGH"),
    ("Success", "HIGH"),
    ("Failure", "MEDIUM"),
    ("Covers", "HIGH"),
]

ABSOLUTE_QUANTIFIERS = (
    "exactly",
    "always",
    "never",
    "must produce",
    "must have",
)

_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_SPEC_ID_RE = re.compile(r"^(" + "|".join(SPEC_PREFIXES) + r")-\d{3}$")
_TASK_ID_RE = re.compile(r"^T\d{3}$")
