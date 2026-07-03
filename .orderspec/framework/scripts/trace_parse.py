#!/usr/bin/env python3
"""trace_parse.py — markdown parsing helpers for traceability."""

import re
from pathlib import Path

from trace_constants import (
    SPEC_PREFIXES, SPEC_PREFIX_RE, ID_RE, AC_COVERS_RE,
    _PATH_RE, _SPEC_ID_RE,
)


def _extract_pathmanifest(plan_file):
    result = []
    in_block = False

    if not Path(plan_file).exists():
        return result

    with open(plan_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if re.match(r"^\s*```\s*pathmanifest\s*$", line):
                in_block = True
                continue
            if in_block and re.match(r"^\s*```\s*$", line):
                break
            if in_block:
                result.append(line)

    return result


def _parse_pathmanifest(plan_file):
    """Return (paths, findings).

    paths: dict repo-relative path -> tag ``[NEW]``/``[MOD]``
    findings: list of error strings
    """
    findings = []
    paths = {}
    manifest = _extract_pathmanifest(plan_file)

    if not manifest:
        findings.append("No pathmanifest block found")
        return paths, findings

    for raw in manifest:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue

        parts = line.split()
        if not parts:
            continue

        path = parts[0]
        tag = ""

        if "[NEW]" in parts:
            tag = "[NEW]"
        if "[MOD]" in parts:
            if tag:
                findings.append(f"Multiple tags on manifest line: {line}")
                continue
            tag = "[MOD]"
        if "[DEL]" in parts:
            if tag:
                findings.append(f"Multiple tags on manifest line: {line}")
                continue
            tag = "[DEL]"

        if path.endswith("/"):
            findings.append(f"Manifest lists directory: {path}")
            continue

        if not tag:
            findings.append(f"Missing [NEW]/[MOD] tag: {path}")
            continue

        if not _PATH_RE.match(path):
            findings.append(f"Bad path token: {path}")
            continue

        paths[path.lstrip("./")] = tag

    return paths, findings


def _extract_defined_ids_from_spec_text(spec_text):
    result = set()
    for line in spec_text.splitlines():
        m = SPEC_PREFIX_RE.match(line)
        if m:
            result.add(f"{m.group(1)}-{m.group(2)}")
    return result


def _extract_all_id_refs(text):
    return {f"{m[0]}-{m[1]}" for m in ID_RE.findall(text)}


def _extract_section(text, header_prefix):
    """Extract markdown section content by header prefix, e.g. '## 9.'."""
    lines = text.splitlines()
    start_idx = -1

    for i, line in enumerate(lines):
        if line.strip().startswith(header_prefix):
            start_idx = i
            break

    if start_idx == -1:
        return ""

    level = len(lines[start_idx]) - len(lines[start_idx].lstrip("#"))
    end_idx = len(lines)

    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith("#"):
            this_level = len(lines[i]) - len(lines[i].lstrip("#"))
            if this_level <= level:
                end_idx = i
                break

    return "\n".join(lines[start_idx:end_idx])


def _parse_field_table(lines, start_idx):
    """Parse a markdown | Field | Value | table after start_idx."""
    i = start_idx

    while i < len(lines) and not lines[i].strip():
        i += 1

    if i >= len(lines):
        return {}

    if not re.match(r"^\s*\|.*\|\s*$", lines[i]):
        return {}

    i += 1

    if i < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i]):
        i += 1

    result = {}

    while i < len(lines):
        m = re.match(r"^\s*\|(.*)\|\s*$", lines[i])
        if not m:
            break

        parts = [p.strip() for p in m.group(1).split("|")]
        if len(parts) >= 2:
            key = parts[0]
            value = " | ".join(parts[1:]) if len(parts) > 2 else parts[1]
            if key:
                result[key] = value

        i += 1

    return result


def _extract_if_records(section_9_text):
    """Extract IF-NNN records and their structured tables from S9."""
    lines = section_9_text.splitlines()
    result = {}

    for i, line in enumerate(lines):
        m = re.match(r"^\s*- \*\*(IF-\d{3})\*\*", line)
        if not m:
            continue

        if_id = m.group(1)
        fields = _parse_field_table(lines, i + 1)
        result[if_id] = {
            "anchor_line": i,
            "fields": fields,
        }

    return result


def _extract_information_model(section_8_text):
    """Extract entities, structures, and value sets from S8.

    Returns:
      {name: set(field_names)}
    """
    lines = section_8_text.splitlines()
    result = {}
    i = 0

    while i < len(lines):
        line = lines[i]
        m = re.match(r"^### (?:Entity|Structure|Value Set):\s*(.+?)\s*$", line)

        if not m:
            i += 1
            continue

        name = m.group(1).strip()
        result[name] = set()
        i += 1

        while i < len(lines):
            if re.match(r"^##\s", lines[i]) or re.match(r"^###\s", lines[i]):
                break

            tbl_m = re.match(r"^\s*\|(.*)\|\s*$", lines[i])
            if tbl_m:
                parts = [p.strip() for p in tbl_m.group(1).split("|")]
                if parts and parts[0].lower() == "field":
                    i += 1
                    if i < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[i]):
                        i += 1

                    while i < len(lines):
                        row_m = re.match(r"^\s*\|(.*)\|\s*$", lines[i])
                        if not row_m:
                            break

                        row_parts = [p.strip() for p in row_m.group(1).split("|")]
                        if row_parts and row_parts[0]:
                            result[name].add(row_parts[0])

                        i += 1

                    continue

            i += 1

    return result


def _extract_ac_inline_covers(section_12_text):
    """Return {AC-ID: [covered spec IDs]} from inline [Covers: ...]."""
    result = {}

    for line in section_12_text.splitlines():
        m_ac = re.match(r"^\s*- \*\*(AC-\d{3})\*\*", line)
        if not m_ac:
            continue

        ac_id = m_ac.group(1)
        covers = []

        for m in AC_COVERS_RE.finditer(line):
            for part in m.group(1).split(","):
                part = part.strip()
                if _SPEC_ID_RE.match(part):
                    covers.append(part)

        result[ac_id] = covers

    return result


def _extract_status_codes(text):
    """Extract contextual HTTP-like status codes from text.

    Context is determined per-clause: text is split by semicolons, newlines,
    and pipe characters (markdown table cell separators). Each clause is
    evaluated independently -- a keyword in one clause does not validate
    status codes in another clause on the same line.
    """
    statuses = set()
    http_keywords = [
        "status",
        "response",
        "returns",
        "return",
        "http",
        "bad request",
        "not found",
        "gone",
        "error",
        "forbidden",
        "unauthorized",
        "unauthenticated",
        "server error",
        "success",
        "created",
        "no content",
        "accepted",
        "conflict",
        "unprocessable",
        "ok",
        "successful",
    ]

    valid_codes = {
        "200", "201", "202", "204",
        "400", "401", "403", "404", "409", "410", "422",
        "500", "503",
    }

    clauses = re.split(r"[;\n|]", text)

    for clause in clauses:
        clause_lower = clause.lower().strip()
        if not clause_lower:
            continue

        numbers = re.findall(r"\b([1-5]\d{2})\b", clause)
        if not numbers:
            continue

        has_keyword = any(kw in clause_lower for kw in http_keywords)
        if not has_keyword:
            continue

        for num in numbers:
            if num in valid_codes:
                statuses.add(num)

    return statuses


def _extract_grid_rows(section_10_text):
    """Parse S10 Contradiction Grid.

    Returns list of (left_id, right_id) tuples.
    """
    rows = []
    in_table = False

    for line in section_10_text.splitlines():
        if re.match(r"^\s*\|.*\|\s*$", line):
            if re.match(r"^\s*\|[\s\-:|]+\|\s*$", line):
                continue

            parts = [p.strip() for p in re.match(r"^\s*\|(.*)\|\s*$", line).group(1).split("|")]

            if not in_table:
                joined = " ".join(parts).lower()
                has_id_ref = bool(ID_RE.search(parts[0])) if parts else False
                header_keywords = ("invariant", "requirement", "pair", "left", "source", "tension", "verdict")
                if not has_id_ref and any(kw in joined for kw in header_keywords):
                    in_table = True
                    continue

            if in_table or (parts and ID_RE.search(parts[0])):
                in_table = True
                pair_text = parts[0] if parts else ""
                ids_in_col = ID_RE.findall(pair_text)

                if len(ids_in_col) >= 2:
                    left_id = f"{ids_in_col[0][0]}-{ids_in_col[0][1]}"
                    right_id = f"{ids_in_col[1][0]}-{ids_in_col[1][1]}"
                    rows.append((left_id, right_id))
                elif len(ids_in_col) == 1:
                    left_id = f"{ids_in_col[0][0]}-{ids_in_col[0][1]}"
                    rows.append((left_id, None))
        else:
            if in_table and line.strip() and not line.strip().startswith("|"):
                in_table = False

    return rows


def _extract_inv_texts(spec_text):
    """Return {INV-ID: anchor line text}."""
    result = {}

    for line in spec_text.splitlines():
        m = re.match(r"^\s*- \*\*(INV-\d{3})\*\*\s*:?\s*(.*)$", line)
        if m:
            result[m.group(1)] = m.group(2)

    return result


def _extract_id_texts(spec_text):
    """Extract {ID: anchor_line_text} from spec text."""
    result = {}
    for line in spec_text.splitlines():
        m = SPEC_PREFIX_RE.match(line)
        if m:
            sid = f"{m.group(1)}-{m.group(2)}"
            result[sid] = line.strip()
    return result


def _sort_spec_id(sid):
    prefix, num = sid.split("-")
    return (SPEC_PREFIXES.index(prefix) if prefix in SPEC_PREFIXES else 999, int(num))
