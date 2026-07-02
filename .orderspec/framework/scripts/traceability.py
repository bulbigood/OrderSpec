#!/usr/bin/env python3
"""traceability.py — deterministic source of truth for OrderSpec traceability.

Portable: Python 3 standard library only. No external dependencies.

This script owns machine-readable feature state under:

    <feature-dir>/.state/

It intentionally supports both path models:

1. Legacy basename mode:
      traceability.py -C <repo> init <feature-basename>
      → <repo>/.orderspec/features/<feature-basename>

2. Current OrderSpec:
      SPECIFY_FEATURE_DIRECTORY / .orderspec/state/active-feature.json / --feature-dir
      → arbitrary repo-relative or absolute feature directory

Prompts should prefer the current model. Legacy basename mode is retained for
older tests and prompts.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

# Import canonical paths from common.py when available.
# traceability.py must remain portable, so keep a local fallback.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from common import ACTIVE_FEATURE_STATE, FEATURES_DIR
except ImportError:
    ACTIVE_FEATURE_STATE = Path(".orderspec") / "state" / "active-feature.json"
    FEATURES_DIR = Path(".orderspec") / "features"

try:
    from common import get_schema_version
    SCHEMA_VERSION = f"v{get_schema_version('traceability')}"
except Exception:
    SCHEMA_VERSION = "v1"

from frontmatter import (
    validate_spec_frontmatter,
    cmd_validate_frontmatter as _frontmatter_cmd,
)

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

_ROOT = Path(__file__).resolve().parent.parent
_FEATURE_DIR_OVERRIDE = None


# ── basic utilities ──────────────────────────────────────────────────────────

def die(msg, rc=2):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(rc)


def script_dir():
    return Path(__file__).resolve().parent


def resolved_root():
    return _ROOT


def _read_json_file(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _repo_relative_or_abs(path_value):
    p = Path(path_value)
    if p.is_absolute():
        return p.resolve()
    return (resolved_root() / p).resolve()


def _active_feature_state_path():
    return resolved_root() / ACTIVE_FEATURE_STATE


def _read_active_feature_dir_from_active_feature_state():
    state_file = _active_feature_state_path()
    data = _read_json_file(state_file)
    if not isinstance(data, dict):
        return None
    value = data.get("feature_directory")
    if not value:
        return None
    return _repo_relative_or_abs(str(value))


def _read_active_feature_dir_from_feature_json():
    """Compatibility wrapper for old internal callers.

    Canonical active feature state is read from ACTIVE_FEATURE_STATE.
    """
    return _read_active_feature_dir_from_active_feature_state()


def resolve_feature_dir(feature=None):
    """Resolve a feature directory.

    Priority:
      1. --feature-dir override
      2. SPECIFY_FEATURE_DIRECTORY
      3. explicit feature argument containing a slash or absolute path
      4. .orderspec/state/active-feature.json if feature is empty or basename matches
      5. legacy <repo>/.orderspec/features/<feature>
    """
    if _FEATURE_DIR_OVERRIDE:
        return _repo_relative_or_abs(_FEATURE_DIR_OVERRIDE)

    env_fd = os.environ.get("SPECIFY_FEATURE_DIRECTORY")
    if env_fd:
        return _repo_relative_or_abs(env_fd)

    if feature:
        fp = Path(feature)
        if fp.is_absolute() or "/" in feature or "\\" in feature:
            return _repo_relative_or_abs(feature)

    active = _read_active_feature_dir_from_feature_json()
    if active is not None:
        if not feature or active.name == feature:
            return active

    if feature:
        return (resolved_root() / FEATURES_DIR / feature).resolve()

    die(
        "feature directory not found. Pass a feature name/path, use --feature-dir, "
        "set SPECIFY_FEATURE_DIRECTORY, or ensure .orderspec/state/active-feature.json "
        "contains feature_directory."
    )


def feature_name(feature=None):
    return resolve_feature_dir(feature).name


def state_dir_for_feature_dir(fdir):
    return Path(fdir) / FEATURE_STATE_DIRNAME


def state_dir(feature=None):
    return state_dir_for_feature_dir(resolve_feature_dir(feature))


def spec_path(feature=None):
    return resolve_feature_dir(feature) / "spec.md"


def plan_path(feature=None):
    return resolve_feature_dir(feature) / "plan.md"


def tasks_path(feature=None):
    return resolve_feature_dir(feature) / "tasks.md"


# ── TSV helpers ──────────────────────────────────────────────────────────────

def _read_tsv_lines(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = f.readlines()

    for i, line in enumerate(lines, start=1):
        if "\r" in line:
            raise ValueError(f"CRLF line ending at line {i}")
        if i > 2 and line.rstrip("\n") == "":
            raise ValueError(f"blank data line at line {i}")

    return lines


def _tsv_lines_to_rows(lines, expected_colnames=None, exact=True):
    rows = []
    if len(lines) < 2:
        return rows

    colnames = lines[1].rstrip("\n").split(TAB)

    if expected_colnames is not None:
        expected_cols = expected_colnames.split(TAB)
        if colnames != expected_cols:
            raise ValueError("wrong column names")
    else:
        expected_cols = colnames

    expected_len = len(expected_cols)

    for i, line in enumerate(lines[2:], start=3):
        line = line.rstrip("\n")
        if not line:
            continue

        parts = line.split(TAB)
        if exact and len(parts) != expected_len:
            raise ValueError(
                f"line {i}: wrong column count: got {len(parts)}, expected {expected_len}"
            )
        if len(parts) < expected_len:
            parts = parts + [""] * (expected_len - len(parts))
        if len(parts) > expected_len:
            parts = parts[:expected_len]

        rows.append(dict(zip(expected_cols, parts)))

    return rows


def read_tsv_body(path, expected_colnames=None):
    lines = _read_tsv_lines(path)
    return _tsv_lines_to_rows(lines, expected_colnames=expected_colnames, exact=True)


def write_tsv_atomic(path, marker, colnames, rows):
    path = Path(path)
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(marker + "\n")
        f.write(colnames + "\n")
        for row in rows:
            f.write(TAB.join(str(c) for c in row) + "\n")
    shutil.move(str(tmp), str(path))


def _read_table(path, kind):
    expected_marker = {
        "mechanisms": MECH_MARKER,
        "trace": TRACE_MARKER,
        "specids": SPECIDS_MARKER,
    }[kind]
    expected_header = {
        "mechanisms": MECH_COLNAMES,
        "trace": TRACE_COLNAMES,
        "specids": SPECIDS_COLNAMES,
    }[kind]

    if not Path(path).exists():
        raise ValueError(f"{path} not found")

    lines = _read_tsv_lines(path)
    if len(lines) < 2:
        raise ValueError(f"{path} empty or missing header")

    marker = lines[0].rstrip("\n")
    header = lines[1].rstrip("\n")

    if marker != expected_marker:
        raise ValueError(f"{kind} wrong version marker")
    if header != expected_header:
        raise ValueError(f"{kind} wrong column names")

    return _tsv_lines_to_rows(lines, expected_colnames=expected_header, exact=True)


# ── markdown helpers ─────────────────────────────────────────────────────────

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

    paths: dict repo-relative path -> tag `[NEW]`/`[MOD]`
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
    """Extract IF-NNN records and their structured tables from §9."""
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
    """Extract entities, structures, and value sets from §8.

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
    evaluated independently — a keyword in one clause does not validate
    status codes in another clause on the same line.

    This prevents the bug where "400 validation error; 403 not owner" on one
    line would extract 403 just because "error" appears elsewhere on the line.
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

    # Split into clauses by semicolons, newlines, and pipe chars.
    # Each clause is evaluated independently for keyword presence.
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
    """Parse §10 Contradiction Grid.

    Returns list of (left_id, right_id) tuples.
    Reads IDs primarily from the first table column, e.g.:
      INV-001 × NFR-001
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
                # A header row uses descriptive words, not spec ID references.
                # Exclude lines containing ID patterns (INV-NNN, REQ-NNN, etc.)
                # from header detection so data rows are not swallowed.
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


def _load_specids(feature=None):
    sdir = state_dir(feature)
    path = sdir / "spec-ids.tsv"
    if not path.exists():
        return {}

    rows = _read_table(path, "specids")
    return {row["spec_id"]: row for row in rows}


def _defined_ids(feature=None):
    specids = _load_specids(feature)
    if specids:
        return set(specids.keys())

    sp = spec_path(feature)
    if not sp.exists():
        return set()

    return _extract_defined_ids_from_spec_text(sp.read_text(encoding="utf-8"))


def _sort_spec_id(sid):
    prefix, num = sid.split("-")
    return (SPEC_PREFIXES.index(prefix) if prefix in SPEC_PREFIXES else 999, int(num))


# ── lint engines ─────────────────────────────────────────────────────────────

def lint_mechanisms(rows):
    errors = []
    seen_ids = set()
    valid_ck = {"direct", "documented"}
    valid_tt = {"unit", "integration", "documented"}
    rows_by_id = {}

    for i, row in enumerate(rows, start=3):
        spec_id = row.get("spec_id", "")
        ck = row.get("coverage_kind", "")
        mech = row.get("mechanism", "")
        files = row.get("primary_files", "")
        tt = row.get("test_type", "")

        if not spec_id:
            errors.append(f"ERROR {i}: empty spec_id")
            continue

        if not _SPEC_ID_RE.match(spec_id):
            errors.append(f"ERROR {i}: bad spec_id \"{spec_id}\"")
            continue

        if spec_id in seen_ids:
            errors.append(f"ERROR {i}: duplicate spec_id \"{spec_id}\"")
            continue

        seen_ids.add(spec_id)
        rows_by_id[spec_id] = row

        prefix = spec_id.split("-")[0]
        if prefix in FORBIDDEN_MECHANISM_PREFIXES:
            errors.append(
                f"ERROR {i}: {prefix} IDs must not have mechanism rows ({spec_id})"
            )

        if not mech:
            errors.append(f"ERROR {i}: empty mechanism for \"{spec_id}\"")

        if ck not in valid_ck and not ck.startswith("delegated:"):
            errors.append(f"ERROR {i}: bad coverage_kind \"{ck}\" for \"{spec_id}\"")
            continue

        if tt not in valid_tt:
            errors.append(f"ERROR {i}: bad test_type \"{tt}\" for \"{spec_id}\"")

        if ck == "direct" and tt not in {"unit", "integration"}:
            errors.append(
                f"ERROR {i}: coverage_kind=direct requires test_type unit|integration "
                f"(got \"{tt}\") for \"{spec_id}\""
            )
        elif ck == "documented" and tt != "documented":
            errors.append(
                f"ERROR {i}: coverage_kind=documented requires test_type=documented "
                f"(got \"{tt}\") for \"{spec_id}\""
            )
        elif tt == "documented" and ck != "documented":
            errors.append(
                f"ERROR {i}: test_type=documented requires coverage_kind=documented "
                f"(got \"{ck}\") for \"{spec_id}\""
            )
        elif ck.startswith("delegated:"):
            tgt = ck[len("delegated:"):]
            if tgt == spec_id:
                errors.append(f"ERROR {i}: delegated coverage points to itself for \"{spec_id}\"")
            if not _SPEC_ID_RE.match(tgt):
                errors.append(f"ERROR {i}: bad delegated target \"{tgt}\" for \"{spec_id}\"")
            if tt not in {"unit", "integration"}:
                errors.append(
                    f"ERROR {i}: delegated coverage requires test_type unit|integration "
                    f"(got \"{tt}\") for \"{spec_id}\""
                )

        if not files:
            errors.append(f"ERROR {i}: empty primary_files for \"{spec_id}\"")
        else:
            if ";" in files:
                errors.append(
                    f"ERROR {i}: primary_files must contain exactly one file, got list \"{files}\" "
                    f"for \"{spec_id}\""
                )
            elif " " in files or not _PATH_RE.match(files):
                errors.append(f"ERROR {i}: bad path token \"{files}\" for \"{spec_id}\"")
            elif files.endswith("/"):
                errors.append(f"ERROR {i}: primary_files must be a file, got directory \"{files}\"")

    # delegated target existence
    for i, row in enumerate(rows, start=3):
        spec_id = row.get("spec_id", "")
        ck = row.get("coverage_kind", "")
        if ck.startswith("delegated:"):
            tgt = ck[len("delegated:"):]
            if _SPEC_ID_RE.match(tgt) and tgt not in rows_by_id:
                errors.append(
                    f"ERROR {i}: delegated target \"{tgt}\" for \"{spec_id}\" has no mechanism row"
                )

    # delegated cycle detection
    graph = {}
    for row in rows:
        spec_id = row.get("spec_id", "")
        ck = row.get("coverage_kind", "")
        if spec_id and ck.startswith("delegated:"):
            graph[spec_id] = ck[len("delegated:"):]

    for sid in graph:
        seen = set()
        cur = sid
        while cur in graph:
            if cur in seen:
                errors.append(f"ERROR: delegated coverage cycle involving \"{sid}\"")
                break
            seen.add(cur)
            cur = graph[cur]

    return errors


def lint_trace(rows):
    errors = []
    seen_ids = set()

    for i, row in enumerate(rows, start=3):
        spec_id = row.get("spec_id", "")
        tasks = row.get("task_ids", "")
        files = row.get("files", "")
        source = row.get("source", "")

        if not spec_id:
            errors.append(f"ERROR {i}: empty spec_id")
            continue

        if not _SPEC_ID_RE.match(spec_id):
            errors.append(f"ERROR {i}: bad spec_id \"{spec_id}\"")
            continue

        if spec_id in seen_ids:
            errors.append(f"ERROR {i}: duplicate spec_id \"{spec_id}\"")
            continue

        seen_ids.add(spec_id)

        if source not in {"tasks.md", "plan.md"}:
            errors.append(f"ERROR {i}: bad source \"{source}\" for \"{spec_id}\"")

        if tasks:
            for t in tasks.split(";"):
                if not _TASK_ID_RE.match(t):
                    errors.append(f"ERROR {i}: bad task_id \"{t}\" for \"{spec_id}\"")
        elif source == "tasks.md":
            errors.append(f"ERROR {i}: empty task_ids but source=tasks.md for \"{spec_id}\"")

        if files:
            for p in files.split(";"):
                if p and not _PATH_RE.match(p):
                    errors.append(f"ERROR {i}: bad path token \"{p}\" for \"{spec_id}\"")

    return errors


def lint_specids(rows):
    errors = []
    seen_ids = set()

    for i, row in enumerate(rows, start=3):
        spec_id = row.get("spec_id", "")
        kind = row.get("kind", "")
        section = row.get("section", "")

        if not spec_id:
            errors.append(f"ERROR {i}: empty spec_id")
            continue

        if not _SPEC_ID_RE.match(spec_id):
            errors.append(f"ERROR {i}: bad spec_id \"{spec_id}\"")
            continue

        if spec_id in seen_ids:
            errors.append(f"ERROR {i}: duplicate spec_id \"{spec_id}\"")
            continue

        seen_ids.add(spec_id)

        if kind not in SPEC_PREFIXES:
            errors.append(f"ERROR {i}: bad kind \"{kind}\"")
        else:
            prefix = spec_id.split("-")[0]
            if kind != prefix:
                errors.append(f"ERROR {i}: kind \"{kind}\" != id prefix \"{prefix}\"")

        if not section:
            errors.append(f"ERROR {i}: empty section for \"{spec_id}\"")

    return errors


def lint_file(path, kind):
    if not Path(path).exists():
        return [f"FATAL: {path} not found"]

    try:
        rows = _read_table(path, kind)
    except ValueError as e:
        return [f"FATAL: {e}"]

    if kind == "mechanisms":
        return lint_mechanisms(rows)
    if kind == "trace":
        return lint_trace(rows)
    if kind == "specids":
        return lint_specids(rows)

    return []


# ── mechanism cross-checks ───────────────────────────────────────────────────

def check_mechanisms_findings(feature=None):
    findings = []
    fdir = resolve_feature_dir(feature)
    sdir = state_dir_for_feature_dir(fdir)
    mech_path = sdir / "mechanisms.tsv"
    specids_path = sdir / "spec-ids.tsv"
    plan_file = fdir / "plan.md"

    if not mech_path.exists():
        findings.append(("M15", "HIGH", "mechanisms.tsv", "mechanisms.tsv not found"))
        return findings

    lint_errs = lint_file(mech_path, "mechanisms")
    for err in lint_errs:
        findings.append(("M15", "HIGH", "mechanisms.tsv", err))

    if lint_errs:
        return findings

    try:
        mech_rows = _read_table(mech_path, "mechanisms")
    except ValueError as e:
        findings.append(("M15", "HIGH", "mechanisms.tsv", str(e)))
        return findings

    mech_by_id = {row["spec_id"]: row for row in mech_rows}

    defined = {}
    if specids_path.exists():
        try:
            for row in _read_table(specids_path, "specids"):
                defined[row["spec_id"]] = row
        except ValueError as e:
            findings.append(("M27", "HIGH", "spec-ids.tsv", str(e)))

    if defined:
        defined_ids = set(defined.keys())

        for sid in sorted(mech_by_id, key=_sort_spec_id):
            if sid not in defined_ids:
                findings.append(
                    ("M27", "HIGH", "mechanisms.tsv", f"{sid} has a mechanism row but is not defined in spec-ids.tsv")
                )

        for sid, row in sorted(defined.items(), key=lambda x: _sort_spec_id(x[0])):
            kind = row.get("kind", sid.split("-")[0])
            if kind in REQUIRED_MECHANISM_PREFIXES and sid not in mech_by_id:
                findings.append(
                    ("M15", "HIGH", "mechanisms.tsv", f"{sid} requires a mechanism row")
                )

    manifest_paths, manifest_errors = _parse_pathmanifest(plan_file)
    for err in manifest_errors:
        findings.append(("M9", "HIGH", "plan.md", err))

    manifest_set = set(manifest_paths.keys())

    for sid, row in sorted(mech_by_id.items(), key=lambda x: _sort_spec_id(x[0])):
        ck = row.get("coverage_kind", "")
        pf = row.get("primary_files", "").lstrip("./")

        if ck == "direct" or ck.startswith("delegated:"):
            if pf not in manifest_set:
                findings.append(
                    (
                        "M16",
                        "HIGH",
                        "mechanisms.tsv",
                        f"{sid} primary file '{pf}' is not listed in plan.md pathmanifest",
                    )
                )

        if ck == "documented":
            if pf not in {"plan.md", str(Path("plan.md"))} and pf not in manifest_set:
                findings.append(
                    (
                        "M26",
                        "MEDIUM",
                        "mechanisms.tsv",
                        f"{sid} documented primary file '{pf}' is neither plan.md nor listed in pathmanifest",
                    )
                )

    # delegated terminal validity
    for sid, row in sorted(mech_by_id.items(), key=lambda x: _sort_spec_id(x[0])):
        ck = row.get("coverage_kind", "")
        if not ck.startswith("delegated:"):
            continue

        seen = set()
        cur = sid
        while True:
            if cur in seen:
                findings.append(
                    ("M17", "HIGH", "mechanisms.tsv", f"delegation cycle starts at {sid}")
                )
                break
            seen.add(cur)

            cur_row = mech_by_id.get(cur)
            if not cur_row:
                findings.append(
                    ("M17", "HIGH", "mechanisms.tsv", f"delegation chain for {sid} points to missing {cur}")
                )
                break

            cur_ck = cur_row.get("coverage_kind", "")
            if cur_ck == "direct" or cur_ck == "documented":
                break

            if cur_ck.startswith("delegated:"):
                cur = cur_ck[len("delegated:"):]
                continue

            findings.append(
                ("M17", "HIGH", "mechanisms.tsv", f"delegation chain for {sid} reaches invalid coverage kind {cur_ck}")
            )
            break

    return findings


# ── commands: init / lint / put / get ────────────────────────────────────────

def cmd_init(feature):
    fdir = resolve_feature_dir(feature)
    if not fdir.exists():
        die(f"feature dir not found: {fdir}")

    sdir = state_dir_for_feature_dir(fdir)
    sdir.mkdir(parents=True, exist_ok=True)

    schema_file = sdir / ".schema"
    if schema_file.exists():
        sv = schema_file.read_text(encoding="utf-8").strip()
        if sv != SCHEMA_VERSION:
            die(f".schema exists with version '{sv}', expected '{SCHEMA_VERSION}'")
        print(f"init: already initialized ({fdir.name}, schema {sv})")
        return

    schema_file.write_text(SCHEMA_VERSION + "\n", encoding="utf-8")
    print(f"init: created {sdir} (schema {SCHEMA_VERSION})")


def cmd_lint(feature):
    sdir = state_dir(feature)
    if not sdir.exists():
        die(f"state not initialized for '{feature or feature_name(feature)}'; run: traceability.py init <feature>")

    schema_file = sdir / ".schema"
    if not schema_file.exists():
        die(f"missing {schema_file}; run: traceability.py init <feature>")

    sv = schema_file.read_text(encoding="utf-8").strip()
    if sv != SCHEMA_VERSION:
        die(f".schema is '{sv}', expected '{SCHEMA_VERSION}'")

    rc = 0

    mech = sdir / "mechanisms.tsv"
    if not mech.exists():
        die(f"mechanisms.tsv not found: {mech}")

    for e in lint_file(mech, "mechanisms"):
        rc = 2
        print(e, file=sys.stderr)

    specids = sdir / "spec-ids.tsv"
    if specids.exists():
        for e in lint_file(specids, "specids"):
            rc = 2
            print(e, file=sys.stderr)

    trace = sdir / "traceability.tsv"
    if trace.exists():
        for e in lint_file(trace, "trace"):
            rc = 2
            print(e, file=sys.stderr)

    if rc != 0:
        print(f"lint: FAIL for {resolve_feature_dir(feature).name}", file=sys.stderr)
        sys.exit(2)

    print(f"lint: OK ({resolve_feature_dir(feature).name})")


def _put_via_lint(feature, kind, basename, marker, colnames, rows=None):
    fdir = resolve_feature_dir(feature)
    if not fdir.exists():
        die(f"feature dir not found: {fdir}")

    sdir = state_dir_for_feature_dir(fdir)
    if not sdir.exists():
        die(f"state not initialized for '{fdir.name}'; run: traceability.py init {fdir.name}")

    target = sdir / basename

    if rows is None:
        rows = []
        expected_cols = len(colnames.split(TAB))
        for line_num, line in enumerate(sys.stdin, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split(TAB)
            if len(parts) != expected_cols:
                print(
                    f"put-{basename}: input line {line_num} has {len(parts)} columns, expected {expected_cols}",
                    file=sys.stderr,
                )
                sys.exit(2)
            rows.append(parts)

    tmp = target.with_suffix(f".tmp.{os.getpid()}")
    write_tsv_atomic(tmp, marker, colnames, rows)

    errs = lint_file(tmp, kind)
    if errs:
        tmp.unlink(missing_ok=True)
        for e in errs:
            print(e, file=sys.stderr)
        print(f"put-{basename}: rejected, {target} not modified", file=sys.stderr)
        sys.exit(2)

    if kind == "trace":
        mtsv = sdir / "mechanisms.tsv"
        if mtsv.exists():
            cov_errs = _lint_coverage(tmp, mtsv)
            if cov_errs:
                tmp.unlink(missing_ok=True)
                for e in cov_errs:
                    print(e, file=sys.stderr)
                print(f"put-{basename}: rejected (coverage), {target} not modified", file=sys.stderr)
                sys.exit(2)

    shutil.move(str(tmp), str(target))
    print(f"put-{basename}: wrote {target}")


def cmd_put_mechanisms(feature):
    _put_via_lint(feature, "mechanisms", "mechanisms.tsv", MECH_MARKER, MECH_COLNAMES)


def cmd_put_spec_ids(feature):
    _put_via_lint(feature, "specids", "spec-ids.tsv", SPECIDS_MARKER, SPECIDS_COLNAMES)


def cmd_put_trace(feature):
    _put_via_lint(feature, "trace", "traceability.tsv", TRACE_MARKER, TRACE_COLNAMES)


def cmd_get(feature, which):
    mapping = {
        "mechanisms": ("mechanisms.tsv", MECH_MARKER, MECH_COLNAMES),
        "spec-ids": ("spec-ids.tsv", SPECIDS_MARKER, SPECIDS_COLNAMES),
        "trace": ("traceability.tsv", TRACE_MARKER, TRACE_COLNAMES),
    }

    if which not in mapping:
        die(f"get: unknown which '{which}' (want mechanisms|spec-ids|trace)", 64)

    basename, marker, colnames = mapping[which]
    sdir = state_dir(feature)
    target = sdir / basename

    if not target.exists():
        die(f"get: no {basename} for feature '{resolve_feature_dir(feature).name}' (run extract/put first)")

    if which == "trace" and _trace_stale(feature):
        die("get: traceability.tsv is stale (tasks.md changed/removed); run extract-trace")

    try:
        rows = _read_table(target, {"mechanisms": "mechanisms", "spec-ids": "specids", "trace": "trace"}[which])
    except ValueError as e:
        die(f"get: {basename}: {e}")

    for row in rows:
        sys.stdout.write(TAB.join(row[c] for c in colnames.split(TAB)) + "\n")


# ── commands: extract spec ids / trace ───────────────────────────────────────

def cmd_extract_spec_ids(feature):
    fdir = resolve_feature_dir(feature)
    spec = fdir / "spec.md"
    if not spec.exists():
        die(f"spec.md not found: {spec}")

    sdir = state_dir_for_feature_dir(fdir)
    if not sdir.exists():
        die(f"state not initialized for '{fdir.name}'; run: traceability.py init {fdir.name}")

    existing_tsv = sdir / "spec-ids.tsv"
    old_ids = set()
    if existing_tsv.exists():
        try:
            old_ids = {row["spec_id"] for row in _read_table(existing_tsv, "specids")}
        except ValueError:
            old_ids = set()

    rows = []
    new_ids = set()

    with open(spec, "r", encoding="utf-8") as f:
        for line in f:
            m = SPEC_PREFIX_RE.match(line)
            if not m:
                continue
            prefix = m.group(1)
            num = m.group(2)
            sid = f"{prefix}-{num}"
            rows.append([sid, prefix, SECTION_MAP.get(prefix, "unknown")])
            new_ids.add(sid)

    removed = old_ids - new_ids
    for sid in sorted(removed, key=_sort_spec_id):
        print(
            f"WARNING: {sid} disappeared from spec.md — verify it was tombstoned "
            f"in §2 Out-of-Scope, not silently renumbered",
            file=sys.stderr,
        )

    _put_via_lint(
        feature,
        "specids",
        "spec-ids.tsv",
        SPECIDS_MARKER,
        SPECIDS_COLNAMES,
        rows=rows,
    )


def _trace_stale(feature):
    tasks = tasks_path(feature)
    trace = state_dir(feature) / "traceability.tsv"

    if not trace.exists():
        return False

    if not tasks.exists():
        print("stale: tasks.md is gone but traceability.tsv remains", file=sys.stderr)
        return True

    if tasks.stat().st_mtime > trace.stat().st_mtime:
        print("stale: tasks.md is newer than traceability.tsv", file=sys.stderr)
        return True

    return False


def cmd_extract_trace(feature):
    fdir = resolve_feature_dir(feature)
    tasks = fdir / "tasks.md"
    if not tasks.exists():
        die(f"tasks.md not found: {tasks}")

    sdir = state_dir_for_feature_dir(fdir)
    if not sdir.exists():
        die(f"state not initialized for '{fdir.name}'; run: traceability.py init {fdir.name}")

    mtsv = sdir / "mechanisms.tsv"
    if not mtsv.exists():
        die(f"extract-trace: mechanisms.tsv not found: {mtsv} (run put-mechanisms first)")

    mech_rows = _read_table(mtsv, "mechanisms")
    ck_of = {}
    pf_of = {}
    bind = {}

    for row in mech_rows:
        sid = row["spec_id"]
        ck = row["coverage_kind"]
        pf = row["primary_files"]
        ck_of[sid] = ck
        pf_of[sid] = pf
        if ck == "direct":
            bind[(pf, sid)] = True

    bug = False
    trace_rows = {}
    seen_ref = set()

    with open(tasks, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = TASK_LINE_RE.match(line)
            if not m:
                continue

            tid = f"T{m.group(1)}"
            parts = line.split(" | ")

            if len(parts) < 3:
                continue

            path = parts[1].strip().lstrip("./")
            refs_str = parts[2].strip() if len(parts) >= 4 else ""

            if not refs_str:
                continue

            if " " in refs_str:
                print(f"extract-trace: spaces in refs of {tid}: <{refs_str}>", file=sys.stderr)
                bug = True
                continue

            refs = refs_str.split(",")
            if len(refs) > 3:
                print(
                    f"extract-trace: task {tid} drives {len(refs)} spec ids (cap 3) <{refs_str}>",
                    file=sys.stderr,
                )
                bug = True
                continue

            for rid in refs:
                if not rid:
                    continue

                if not _SPEC_ID_RE.match(rid):
                    print(f"extract-trace: bad ref id {rid} in {tid}", file=sys.stderr)
                    bug = True
                    continue

                if (rid, tid) in seen_ref:
                    print(f"extract-trace: duplicate ref {rid} within {tid}", file=sys.stderr)
                    bug = True
                    continue

                seen_ref.add((rid, tid))

                if rid not in ck_of:
                    print(f"extract-trace: ref {rid} in {tid} is not a known mechanism", file=sys.stderr)
                    bug = True
                    continue

                if ck_of[rid] == "documented":
                    print(
                        f"extract-trace: ref {rid} in {tid} is documented; documented ids must NOT be tasked",
                        file=sys.stderr,
                    )
                    bug = True
                    continue

                if ck_of[rid].startswith("delegated:"):
                    print(
                        f"extract-trace: ref {rid} in {tid} is delegated; task its delegate, not the delegated id",
                        file=sys.stderr,
                    )
                    bug = True
                    continue

                if (path, rid) not in bind:
                    print(
                        f"extract-trace: ref {rid} on {tid} not in its primary_files "
                        f"(path={path}); filler/mis-attributed ref",
                        file=sys.stderr,
                    )
                    bug = True
                    continue

                trace_rows.setdefault(
                    rid,
                    {"tasks": set(), "files": set(), "source": "tasks.md"},
                )
                trace_rows[rid]["tasks"].add(tid)
                trace_rows[rid]["files"].add(path)

    if bug:
        sys.exit(3)

    for sid, ck in ck_of.items():
        if ck == "documented" and sid not in trace_rows:
            pf = pf_of.get(sid, "")
            trace_rows[sid] = {
                "tasks": set(),
                "files": {pf} if pf else set(),
                "source": "plan.md",
            }

    out_rows = []
    for sid in sorted(trace_rows.keys(), key=_sort_spec_id):
        r = trace_rows[sid]
        out_rows.append([
            sid,
            ";".join(sorted(r["tasks"])),
            ";".join(sorted(f for f in r["files"] if f)),
            r["source"],
        ])

    tmp = (sdir / "traceability.tsv").with_suffix(f".tmp.{os.getpid()}")
    write_tsv_atomic(tmp, TRACE_MARKER, TRACE_COLNAMES, out_rows)

    errs = lint_file(tmp, "trace")
    if errs:
        tmp.unlink(missing_ok=True)
        for e in errs:
            print(e, file=sys.stderr)
        print("extract-trace: rejected (format), traceability.tsv not modified", file=sys.stderr)
        sys.exit(2)

    cov_errs = _lint_coverage(tmp, mtsv)
    if cov_errs:
        tmp.unlink(missing_ok=True)
        for e in cov_errs:
            print(e, file=sys.stderr)
        print("extract-trace: rejected (coverage), traceability.tsv not modified", file=sys.stderr)
        sys.exit(2)

    shutil.move(str(tmp), str(sdir / "traceability.tsv"))
    print(f"extract-trace: wrote {sdir / 'traceability.tsv'}")


def _lint_coverage(tracef, mtsv):
    errors = []
    mech_rows = _read_table(mtsv, "mechanisms")
    trace_rows = _read_table(tracef, "trace")

    mech = {}
    deleg = {}
    taskcov = {}
    plancov = {}

    for row in mech_rows:
        sid = row["spec_id"]
        ck = row["coverage_kind"]
        mech[sid] = ck
        if ck.startswith("delegated:"):
            deleg[sid] = ck[len("delegated:"):]

    for row in trace_rows:
        sid = row["spec_id"]
        src = row["source"]
        if src == "tasks.md":
            taskcov[sid] = True
        if src == "plan.md":
            plancov[sid] = True

    for sid, ck in mech.items():
        if ck == "direct":
            if sid not in taskcov:
                errors.append(f"coverage: direct {sid} uncovered")
        elif ck == "documented":
            if sid in taskcov:
                errors.append(f"coverage: documented {sid} must NOT have a task")
            if sid not in plancov:
                errors.append(f"coverage: documented {sid} missing plan.md row")
        elif ck.startswith("delegated:"):
            tgt = deleg[sid]
            if tgt not in taskcov and mech.get(tgt) != "documented":
                errors.append(f"coverage: delegated {sid} -> {tgt} uncovered")

    return errors


# ── commands: render / check-plan / check-mechanisms ─────────────────────────

def cmd_render(feature):
    fdir = resolve_feature_dir(feature)
    sdir = state_dir_for_feature_dir(fdir)

    if not sdir.exists():
        die(f"state not initialized for '{fdir.name}'; run: traceability.py init {fdir.name}")

    tracef = sdir / "traceability.tsv"
    mtsv = sdir / "mechanisms.tsv"

    if not tracef.exists():
        die(f"render: no traceability.tsv for '{fdir.name}'; run extract-trace")

    if _trace_stale(feature):
        print("render: traceability.tsv is stale, not rendering", file=sys.stderr)
        sys.exit(2)

    for e in lint_file(tracef, "trace"):
        print(e, file=sys.stderr)
        sys.exit(2)

    kind_of = {}
    if mtsv.exists():
        for e in lint_file(mtsv, "mechanisms"):
            print(e, file=sys.stderr)
            sys.exit(2)
        for row in _read_table(mtsv, "mechanisms"):
            kind_of[row["spec_id"]] = row["coverage_kind"]

    trace_rows = _read_table(tracef, "trace")

    lines = [
        "<!-- DO NOT EDIT — generated by traceability.py render from .state/*.tsv -->",
        f"# Traceability — {fdir.name}",
        "",
        "| spec_id | kind | tasks | files | source |",
        "|---------|------|-------|-------|--------|",
    ]

    counts = {"direct": 0, "documented": 0, "delegated": 0, "total": 0}

    for row in trace_rows:
        sid = row["spec_id"]
        k = kind_of.get(sid, "?")
        tasks = row["task_ids"] or "—"
        files = row["files"] or "—"
        source = row["source"]

        lines.append(
            f"| {sid} | {k} | {tasks.replace('|', '\\|')} | "
            f"{files.replace('|', '\\|')} | {source} |"
        )

        counts["total"] += 1
        if k == "direct":
            counts["direct"] += 1
        elif k == "documented":
            counts["documented"] += 1
        elif k.startswith("delegated:"):
            counts["delegated"] += 1

    lines.append("")
    lines.append(
        f"{counts['total']} mechanisms · {counts['direct']} direct · "
        f"{counts['documented']} documented · {counts['delegated']} delegated"
    )
    lines.append("")

    target = sdir / "traceability.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"render: wrote {target}")


def cmd_check_plan(feature):
    fdir = resolve_feature_dir(feature)
    plan = fdir / "plan.md"

    if not plan.exists():
        die(f"check-plan: plan.md not found: {plan}")

    rc = 0
    manifest_paths, manifest_errors = _parse_pathmanifest(plan)

    for err in manifest_errors:
        print(f"check-plan: ERROR — {err}", file=sys.stderr)
        rc = 1

    for path, tag in manifest_paths.items():
        full_path = resolved_root() / path

        if tag == "[MOD]" and not full_path.exists():
            print(f"check-plan: ERROR — [MOD] path does not exist: {path}", file=sys.stderr)
            rc = 1

        if tag == "[NEW]" and full_path.exists():
            print(f"check-plan: ERROR — [NEW] path already exists: {path}", file=sys.stderr)
            rc = 1

    if rc == 0:
        print(f"check-plan: OK ({fdir.name})")
    else:
        print(f"check-plan: FAIL ({fdir.name}) — see errors above", file=sys.stderr)

    sys.exit(rc)


def cmd_check_mechanisms(feature):
    findings = check_mechanisms_findings(feature)
    if not findings:
        print(f"check-mechanisms: OK ({resolve_feature_dir(feature).name})")
        return

    for check, severity, location, message in findings:
        print(f"[{severity}] {check} ({location}): {message}", file=sys.stderr)

    print(f"check-mechanisms: FAIL ({resolve_feature_dir(feature).name})", file=sys.stderr)
    sys.exit(1)

def cmd_summarize_mechanisms(feature, json_out=False):
    sdir = state_dir(feature)
    mech_path = sdir / "mechanisms.tsv"

    if not mech_path.exists():
        die(f"summarize-mechanisms: mechanisms.tsv not found: {mech_path}")

    errs = lint_file(mech_path, "mechanisms")
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        die("summarize-mechanisms: mechanisms.tsv failed lint", 2)

    try:
        rows = _read_table(mech_path, "mechanisms")
    except ValueError as e:
        die(f"summarize-mechanisms: {e}")

    summary = {
        "total": len(rows),
        "direct": 0,
        "documented": 0,
        "delegated": 0,
        "by_prefix": {},
    }

    for row in rows:
        sid = row["spec_id"]
        prefix = sid.split("-")[0]
        ck = row["coverage_kind"]

        summary["by_prefix"].setdefault(prefix, {
            "total": 0,
            "direct": 0,
            "documented": 0,
            "delegated": 0,
        })

        summary["by_prefix"][prefix]["total"] += 1

        if ck == "direct":
            summary["direct"] += 1
            summary["by_prefix"][prefix]["direct"] += 1
        elif ck == "documented":
            summary["documented"] += 1
            summary["by_prefix"][prefix]["documented"] += 1
        elif ck.startswith("delegated:"):
            summary["delegated"] += 1
            summary["by_prefix"][prefix]["delegated"] += 1

    if json_out:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            f"mechanisms: total={summary['total']} "
            f"direct={summary['direct']} "
            f"documented={summary['documented']} "
            f"delegated={summary['delegated']}"
        )

        for prefix in sorted(summary["by_prefix"]):
            p = summary["by_prefix"][prefix]
            print(
                f"{prefix}: total={p['total']} "
                f"direct={p['direct']} "
                f"documented={p['documented']} "
                f"delegated={p['delegated']}"
            )

# ── validate ─────────────────────────────────────────────────────────────────

def cmd_validate(args):
    feature = args.feature
    fdir = resolve_feature_dir(feature)
    spec = fdir / "spec.md"
    plan = fdir / "plan.md"
    tasks = fdir / "tasks.md"

    if not spec.exists():
        die(f"validate: spec.md not found: {spec}")

    have_plan = plan.exists()
    have_tasks = tasks.exists()

    stage = args.stage
    if not stage:
        if have_tasks and have_plan:
            stage = "tasks"
        elif have_plan:
            stage = "plan"
        else:
            stage = "spec"

    if stage not in {"spec", "plan", "tasks"}:
        die(f"validate: invalid stage '{stage}' (use spec|plan|tasks)", 64)

    if stage in {"plan", "tasks"} and not have_plan:
        die(f"validate: stage={stage} requires plan.md (missing: {plan})", 2)

    if stage == "tasks" and not have_tasks:
        die(f"validate: stage=tasks requires tasks.md (missing: {tasks})", 2)

    findings = []

    def add(check, severity, location, message):
        findings.append({
            "check": check,
            "severity": severity,
            "location": location,
            "message": message,
        })

    spec_text = spec.read_text(encoding="utf-8")
    defined_ids = _defined_ids(feature)
    anchor_ids = _extract_defined_ids_from_spec_text(spec_text)

    if not defined_ids:
        defined_ids = anchor_ids

    # M6 unresolved markers
    for i, line in enumerate(spec_text.splitlines(), start=1):
        if re.search(r"\bQ-\d+\b|\[NEEDS CLARIFICATION", line):
            add("M6", "HIGH", f"spec.md:{i}", f"Unresolved clarification: {line.strip()}")

    # M28: YAML frontmatter metadata validation
    fm_errors = validate_spec_frontmatter(spec_text)
    for field, message in fm_errors:
        add("M28", "HIGH", "spec.md:frontmatter", message)

    # M1: REQ covered by UJ Covers lines
    req_ids = {sid for sid in defined_ids if sid.startswith("REQ-")}
    covers_ids = set()
    for line in spec_text.splitlines():
        if COVERS_RE.match(line):
            covers_ids |= _extract_all_id_refs(line)

    for sid in sorted(req_ids, key=_sort_spec_id):
        if sid not in covers_ids:
            add("M1", "HIGH", "spec.md", f"{sid} is not listed in any UJ 'Covers'")

    # M1a: AC inline covers
    ac_ids = {sid for sid in defined_ids if sid.startswith("AC-")}
    ac_inline_seen = set()
    for line in spec_text.splitlines():
        m = re.match(r"^\s*- \*\*(AC-\d{3})\*\*", line)
        if not m:
            continue
        ac_id = m.group(1)
        ac_inline_seen.add(ac_id)
        cm = AC_COVERS_RE.search(line)
        if not cm:
            add("M1a", "HIGH", "spec.md", f"{ac_id} has no inline [Covers: ...]")
            continue
        refs = _extract_all_id_refs(cm.group(1))
        if not refs:
            add("M1a", "HIGH", "spec.md", f"{ac_id} inline [Covers: ...] contains no valid spec IDs")

    for sid in sorted(ac_ids - ac_inline_seen, key=_sort_spec_id):
        add("M1a", "HIGH", "spec.md", f"{sid} is defined but no AC anchor line was parsed")

    # Sections used by spec-stage semantic checks
    section_8 = _extract_section(spec_text, "## 8.")
    section_9 = _extract_section(spec_text, "## 9.")
    section_10 = _extract_section(spec_text, "## 10.")
    section_12 = _extract_section(spec_text, "## 12.")

    # M18: IF required fields
    if_records = _extract_if_records(section_9) if section_9 else {}

    for if_id, rec in if_records.items():
        fields = rec["fields"]

        for field_name, sev in IF_REQUIRED_FIELDS:
            if field_name not in fields or not fields[field_name].strip():
                add("M18", sev, "spec.md:§9", f"{if_id} missing required field '{field_name}'")

    # AC inline Covers map for IF linkage checks
    ac_inline_covers = _extract_ac_inline_covers(section_12) if section_12 else {}

    # M19: IF-AC HTTP status code cross-check
    if_to_acs = {}

    for ac_id, covers_list in ac_inline_covers.items():
        for ref in covers_list:
            if_to_acs.setdefault(ref, set()).add(ac_id)

    for if_id, rec in if_records.items():
        fields = rec["fields"]
        kind = fields.get("Kind", "")

        if not kind:
            continue

        kind_lower = kind.lower()
        if "http" not in kind_lower and "endpoint" not in kind_lower:
            continue

        if_statuses = set()
        if_statuses |= _extract_status_codes(fields.get("Success", ""))
        if_statuses |= _extract_status_codes(fields.get("Failure", ""))

        covering_acs = if_to_acs.get(if_id, set())

        for ac_id in covering_acs:
            for line in section_12.splitlines():
                if line.strip().startswith(f"- **{ac_id}**"):
                    ac_statuses = _extract_status_codes(line)
                    for st in ac_statuses:
                        if st not in if_statuses:
                            add(
                                "M19",
                                "MEDIUM",
                                "spec.md:§12",
                                f"{ac_id} references status {st} for {if_id} but it is not in IF Success/Failure",
                            )
                    break

    # M29: IF->AC status code coverage (every status in IF must be covered by at least one AC)
    # Success codes: HIGH severity (must be tested)
    # Failure codes: MEDIUM severity (should be tested, but not all failure paths require AC)
    for if_id, rec in if_records.items():
        fields = rec["fields"]
        kind = fields.get("Kind", "")

        if not kind:
            continue

        kind_lower = kind.lower()
        if "http" not in kind_lower and "endpoint" not in kind_lower:
            continue

        if_success_statuses = _extract_status_codes(fields.get("Success", ""))
        if_failure_statuses = _extract_status_codes(fields.get("Failure", ""))
        if_all_statuses = if_success_statuses | if_failure_statuses

        covering_acs = if_to_acs.get(if_id, set())

        # Collect all statuses referenced by covering ACs
        ac_statuses_for_if = set()
        for ac_id in covering_acs:
            for line in section_12.splitlines():
                if line.strip().startswith(f"- **{ac_id}**"):
                    ac_statuses_for_if |= _extract_status_codes(line)
                    break

        # Check Success codes: every success status must be covered by at least one AC
        for st in sorted(if_success_statuses):
            if st not in ac_statuses_for_if:
                add(
                    "M29",
                    "HIGH",
                    "spec.md:\u00a79",
                    f"{if_id} Success status {st} is not covered by any AC",
                )

        # Check Failure codes: warn if not covered (not all failure paths need AC)
        for st in sorted(if_failure_statuses):
            if st not in ac_statuses_for_if:
                add(
                    "M29",
                    "MEDIUM",
                    "spec.md:\u00a79",
                    f"{if_id} Failure status {st} is not covered by any AC (consider adding AC for this failure path)",
                )

    # M20: every IF must be covered by at least one AC via inline Covers
    for if_id in if_records:
        if if_id not in if_to_acs or not if_to_acs[if_id]:
            add("M20", "HIGH", "spec.md:§9", f"{if_id} is not covered by any AC via [Covers: ...]")

    # M21: IF Covers/Related references must exist
    for if_id, rec in if_records.items():
        fields = rec["fields"]
        link_field = fields.get("Covers") or fields.get("Related") or ""

        if not link_field:
            continue

        for m in ID_RE.finditer(link_field):
            ref_id = f"{m.group(1)}-{m.group(2)}"
            if ref_id not in defined_ids:
                add("M21", "HIGH", "spec.md:§9", f"{if_id} Covers references unknown {ref_id}")

    # M22: AC field alignment with §8 Information Model
    info_model = _extract_information_model(section_8) if section_8 else {}
    all_known_fields = set()

    for fld_set in info_model.values():
        all_known_fields |= fld_set

    envelope_fields = {
        "results",
        "page",
        "limit",
        "totalPages",
        "totalResults",
        "total",
        "data",
        "items",
        "count",
        "nextCursor",
        "prevCursor",
        "cursor",
    }

    ac_field_patterns = [
        r"contains?\s+`(\w+)`",
        r"including\s+`(\w+)`",
        r"with\s+`(\w+)`",
        r"returned.*`(\w+)`",
        r"includes?\s+`(\w+)`",
        r"`(\w+)`\s+field",
    ]

    for line in section_12.splitlines():
        m_ac = re.match(r"^\s*- \*\*(AC-\d{3})\*\*", line)
        if not m_ac:
            continue

        ac_id = m_ac.group(1)

        for pattern in ac_field_patterns:
            for m in re.finditer(pattern, line, re.IGNORECASE):
                field_name = m.group(1)

                if (
                    field_name not in all_known_fields
                    and field_name not in envelope_fields
                    and field_name.lower() not in {x.lower() for x in all_known_fields}
                ):
                    add(
                        "M22",
                        "LOW",
                        "spec.md:§12",
                        f"{ac_id} checks field '{field_name}' not found in §8 Information Model",
                    )

    # M23: Contradiction Grid reference validity
    grid_rows = _extract_grid_rows(section_10) if section_10 else []

    for left_id, right_id in grid_rows:
        if left_id and left_id not in anchor_ids:
            add("M23", "MEDIUM", "spec.md:§10", f"Grid left ID {left_id} not defined in spec")

        if right_id and right_id not in anchor_ids:
            add("M23", "MEDIUM", "spec.md:§10", f"Grid right ID {right_id} not defined in spec")

    # M24: Grid completeness for absolute-quantifier INV
    inv_texts = _extract_inv_texts(spec_text)
    grid_left_ids = {left_id for left_id, _ in grid_rows}

    for inv_id, text in inv_texts.items():
        text_lower = text.lower()
        if any(q in text_lower for q in ABSOLUTE_QUANTIFIERS):
            if inv_id not in grid_left_ids:
                add(
                    "M24",
                    "MEDIUM",
                    "spec.md:§10",
                    f"{inv_id} uses absolute quantifier but has no row in Contradiction Grid",
                )

    # M25: duplicate grid rows
    if len(grid_rows) != len(set(grid_rows)):
        add("M25", "MEDIUM", "spec.md:§10", "Duplicate rows found in Contradiction Grid")

    # M13 placeholder residue
    files_for_placeholder_scan = [spec]
    if have_plan:
        files_for_placeholder_scan.append(plan)
    if have_tasks:
        files_for_placeholder_scan.append(tasks)

    for f in files_for_placeholder_scan:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"TODO|TKTK|\?\?\?|<placeholder>|\[path/to/|NEEDS CLARIFICATION|Optional forced upstream-gate warning|verdict: \.\.\.|semicolon-separated|\[Failure outcomes\]|\[Success outcomes\]|None \(.*\)", line):
                sev = "MEDIUM" if "<placeholder>" in line or "[path/to/" in line else "LOW"
                add("M13", sev, f"{f.name}:{i}", f"Placeholder residue: {line.strip()[:100]}")

    if stage in {"plan", "tasks"}:
        plan_text = plan.read_text(encoding="utf-8")
        plan_refs = _extract_all_id_refs(plan_text)

        for sid in sorted(plan_refs - defined_ids, key=_sort_spec_id):
            add("M5", "HIGH", "plan.md", f"{sid} cited in plan.md but not defined in spec-ids.tsv/spec.md anchors")

        manifest_paths, manifest_errors = _parse_pathmanifest(plan)
        for err in manifest_errors:
            add("M9", "HIGH", "plan.md", err)

        for path, tag in manifest_paths.items():
            full_path = resolved_root() / path
            if tag == "[MOD]" and not full_path.exists():
                add("M10", "HIGH", "plan.md", f"[MOD] path '{path}' does not exist in repo")
            elif tag == "[NEW]" and full_path.exists():
                add("M10", "HIGH", "plan.md", f"[NEW] path '{path}' already exists in repo")

        for check, severity, location, message in check_mechanisms_findings(feature):
            add(check, severity, location, message)

    if stage == "tasks":
        tasks_text = tasks.read_text(encoding="utf-8")
        task_lines = []

        for i, line in enumerate(tasks_text.splitlines(), start=1):
            if TASK_LINE_RE.match(line):
                task_lines.append((i, line))

        task_refs = set()
        task_paths = set()

        for line_num, line in task_lines:
            parts = line.split(" | ")

            if len(parts) >= 2:
                p = parts[1].strip().lstrip("./")
                if p:
                    task_paths.add(p)

            if len(parts) >= 4:
                refs_str = parts[2].strip()
                if refs_str and " " not in refs_str:
                    for rid in refs_str.split(","):
                        rid = rid.strip()
                        if _SPEC_ID_RE.match(rid):
                            task_refs.add(rid)

        # Load coverage kind from mechanisms.tsv when available.
        # Missing mechanisms are reported separately by M15 in plan-stage checks.
        ck_of = {}
        mtsv = state_dir(feature) / "mechanisms.tsv"

        if mtsv.exists() and not lint_file(mtsv, "mechanisms"):
            try:
                for row in _read_table(mtsv, "mechanisms"):
                    ck_of[row["spec_id"]] = row.get("coverage_kind", "")
            except ValueError:
                ck_of = {}

        edge_ids = {sid for sid in defined_ids if sid.startswith("EDGE-")}
        inv_ids = {sid for sid in defined_ids if sid.startswith("INV-")}
        uj_ids = {sid for sid in defined_ids if sid.startswith("UJ-")}

        # M2: AC -> tasks for direct/default coverage
        for sid in sorted(ac_ids, key=_sort_spec_id):
            ck = ck_of.get(sid, "")
            if (not ck or ck == "direct") and sid not in task_refs:
                add("M2", "HIGH", "tasks.md", f"{sid} is not referenced by any task")

        # M3: EDGE/INV -> tasks for direct/default coverage
        for sid in sorted(edge_ids | inv_ids, key=_sort_spec_id):
            ck = ck_of.get(sid, "")
            if (not ck or ck == "direct") and sid not in task_refs:
                add("M3", "HIGH", "tasks.md", f"{sid} is not referenced by any task")

        # M4: [USn] tasks reference at least one spec ID
        for line_num, line in task_lines:
            if not re.search(r"\[US\d+\]", line):
                continue

            parts = line.split(" | ")
            refs_str = parts[2].strip() if len(parts) >= 4 else ""
            has_ref = False

            if refs_str and " " not in refs_str:
                has_ref = any(_SPEC_ID_RE.match(r.strip()) for r in refs_str.split(",") if r.strip())

            if not has_ref:
                tid = re.search(r"T\d{3}", line)
                add(
                    "M4",
                    "MEDIUM",
                    f"tasks.md:{line_num}",
                    f"Story task {tid.group(0) if tid else '???'} references no spec ID",
                )

        for sid in sorted(task_refs - defined_ids, key=_sort_spec_id):
            add("M5", "HIGH", "tasks.md", f"{sid} cited in tasks.md but not defined in spec-ids.tsv/spec.md anchors")

        manifest_paths, _ = _parse_pathmanifest(plan)

        for p in sorted(task_paths):
            if p not in manifest_paths:
                add("M8", "HIGH", "tasks.md", f"Path '{p}' used in tasks.md but not in plan.md manifest")

        # M12: [P] tasks sharing paths
        p_paths = {}

        for line_num, line in task_lines:
            if not re.search(r"T\d{3} \[P\]", line):
                continue

            tid_m = re.search(r"T\d{3}", line)
            if not tid_m:
                continue

            tid = tid_m.group(0)
            parts = line.split(" | ")

            if len(parts) < 2:
                continue

            p = parts[1].strip()

            if p in p_paths:
                add("M12", "MEDIUM", "tasks.md", f"[P] tasks {p_paths[p]} and {tid} both touch '{p}'")
            else:
                p_paths[p] = tid

        # M14: [USn] -> UJ-00n
        us_labels = set()

        for line_num, line in task_lines:
            for m in re.finditer(r"\[US(\d+)\]", line):
                us_labels.add(m.group(1))

        for us in sorted(us_labels, key=lambda x: int(x)):
            uj = f"UJ-{int(us):03d}"
            if uj not in uj_ids:
                add("M14", "HIGH", "tasks.md", f"Label [US{us}] has no matching {uj} in spec.md")

        # M7: task numbering
        nums = []

        for _, line in task_lines:
            m = re.search(r"T(\d{3})", line)
            if m:
                nums.append(int(m.group(1)))

        seen_nums = set()
        dupes = set()

        for n in nums:
            if n in seen_nums:
                dupes.add(n)
            seen_nums.add(n)

        for n in sorted(dupes):
            add("M7", "MEDIUM", "tasks.md", f"Duplicate task ID T{n:03d}")

        if nums:
            for n in range(min(nums), max(nums) + 1):
                if n not in seen_nums:
                    add("M7", "MEDIUM", "tasks.md", f"Gap in task numbering: T{n:03d}")

    # M30: EDGE without AC coverage or explicit defer
    edge_ids = {sid for sid in defined_ids if sid.startswith("EDGE-")}
    id_texts = _extract_id_texts(spec_text)
    ac_covers_targets = set()
    for covers_list in ac_inline_covers.values():
        ac_covers_targets.update(covers_list)

    for sid in sorted(edge_ids, key=_sort_spec_id):
        text = id_texts.get(sid, "").lower()
        is_deferred = "deferred" in text
        is_covered = (sid in ac_covers_targets) or bool(re.search(r"covered by\s+ac-\d{3}", text))
        if not is_covered and not is_deferred:
            add("M30", "MEDIUM", "spec.md:§11", f"{sid} has no AC coverage and is not marked deferred")

    # M31: at most 2 UJs may be P1
    uj_p1_ids = []
    for line in spec_text.splitlines():
        m_uj = re.match(r"^\s*- \*\*(UJ-\d{3})\*\*", line)
        if not m_uj:
            continue
        if re.search(r"Priority:\s*P1", line, re.IGNORECASE):
            uj_p1_ids.append(m_uj.group(1))

    if len(uj_p1_ids) > 2:
        add("M31", "MEDIUM", "spec.md:\u00a712", f"More than 2 P1 UJs found ({len(uj_p1_ids)}): {', '.join(uj_p1_ids)}")

    # M32: DEC must have Affects and Rationale sub-items
    spec_lines = spec_text.splitlines()
    for i, line in enumerate(spec_lines):
        m_dec = re.match(r"^\s*- \*\*(DEC-\d{3})\*\*", line)
        if not m_dec:
            continue
        dec_id = m_dec.group(1)
        has_affects = False
        has_rationale = False
        for j in range(i, min(i + 10, len(spec_lines))):
            sub = spec_lines[j]
            if j > i and re.match(r"^\s*- \*\*\w+-\d{3}\*\*", sub):
                break
            if re.search(r"\*\*Affects\*\*", sub, re.IGNORECASE):
                has_affects = True
            if re.search(r"\*\*Rationale\*\*", sub, re.IGNORECASE):
                has_rationale = True
        if not has_affects:
            add("M32", "MEDIUM", "spec.md:\u00a714", f"{dec_id} missing required '**Affects**' sub-item")
        if not has_rationale:
            add("M32", "MEDIUM", "spec.md:\u00a714", f"{dec_id} missing required '**Rationale**' sub-item")

    # M11 timestamp drift
    if have_plan and spec.stat().st_mtime > plan.stat().st_mtime:
        add("M11", "MEDIUM", "spec.md/plan.md", "spec.md modified after plan.md")

    if have_plan and have_tasks and plan.stat().st_mtime > tasks.stat().st_mtime:
        add("M11", "MEDIUM", "plan.md/tasks.md", "plan.md modified after tasks.md")

    total = len(findings)
    nc = sum(1 for f in findings if f["severity"] == "CRITICAL")
    nh = sum(1 for f in findings if f["severity"] == "HIGH")
    nm = sum(1 for f in findings if f["severity"] == "MEDIUM")
    nl = sum(1 for f in findings if f["severity"] == "LOW")

    exit_code = 1 if (nc + nh) > 0 else 0
    pass_allowed = nc == 0
    block_required = nc > 0
    verdict_floor = "PASS" if nc == 0 and nh == 0 else ("BLOCK" if nc > 0 else "ROUTING_REQUIRED")

    if args.json:
        output = {
            "stage": stage,
            "scope": {"spec": True, "plan": have_plan, "tasks": have_tasks},
            "summary": {
                "total": total,
                "critical": nc,
                "high": nh,
                "medium": nm,
                "low": nl,
                "exit_code": exit_code,
                "pass_allowed": pass_allowed,
                "block_required": block_required,
                "verdict_floor": verdict_floor,
            },
            "findings": findings,
        }
        print(json.dumps(output))
    else:
        print(f"=== validate: {fdir} (stage={stage}) ===")
        print(f"Scope: spec=true plan={have_plan} tasks={have_tasks}")
        if total == 0:
            print("RESULT: CLEAN — no mechanical findings.")
        else:
            print(f"Findings: {total} (CRITICAL={nc} HIGH={nh} MEDIUM={nm} LOW={nl})")
            for f in findings:
                print(f"[{f['severity']}] {f['check']} ({f['location']}): {f['message']}")

    sys.exit(exit_code)

# ── mark-consumed ────────────────────────────────────────────────────────────

def cmd_mark_consumed(args):
    """Mark a gate report file as CONSUMED_STALE after /order.plan used it."""
    report_path = Path(args.report)
    if not report_path.exists():
        die(f"mark-consumed: report file not found: {report_path}")
    
    marker = f"""# CONSUMED_STALE — {report_path.name}

This is not a PASS verdict.

The previous `/order.plan-check` report was consumed by `/order.plan` and is now stale.
Run `/order.plan-check` for a fresh verdict.
"""
    report_path.write_text(marker, encoding="utf-8")
    print(f"mark-consumed: wrote CONSUMED_STALE marker to {report_path}")


# ── diff-summary ─────────────────────────────────────────────────────────────

def _git_show_spec(repo_root, git_ref, spec_rel_path):
    """Read spec.md content at a given git ref. Returns text or dies."""
    import subprocess as sp
    try:
        result = sp.run(
            ["git", "show", f"{git_ref}:{spec_rel_path}"],
            capture_output=True, text=True, cwd=str(repo_root)
        )
        if result.returncode != 0:
            die(f"diff-summary: cannot read spec.md at {git_ref}: {result.stderr.strip()}")
        return result.stdout
    except FileNotFoundError:
        die("diff-summary: git not found in PATH")

def _print_diff_summary_markdown(summary):
    print("## Contract Change Summary")
    print()
    print(f"**Feature**: `{summary['feature']}`")
    print(f"**Comparison**: `{summary['old_ref']}` → `{summary['new_ref']}`")
    print()

    if summary["added"]:
        print("### Added")
        for item in summary["added"]:
            print(f"- `{item['id']}`: {item['text']}")
        print()

    if summary["removed"]:
        print("### Removed")
        for item in summary["removed"]:
            print(f"- `{item['id']}`: {item['text']}")
        print()

    if summary["changed"]:
        print("### Changed")
        for item in summary["changed"]:
            details_str = "; ".join(item["details"])
            print(f"- `{item['id']}` ({details_str})")
        print()

    ds = summary["downstream_regeneration"]
    print("### Downstream impact")
    print(f"- `plan.md`: {'stale' if ds['plan_md'] else 'current'}")
    print(f"- `tasks.md`: {'stale' if ds['tasks_md'] else 'current'}")
    print(f"- tests: {'likely stale' if ds['tests'] else 'current'}")
    print()
    print(f"**Requires approval**: {'Yes' if summary['requires_approval'] else 'No'}")

def cmd_diff_summary(args):
    """Generate a Contract Change Summary by comparing spec.md at two git revisions."""
    feature = args.feature
    fdir = resolve_feature_dir(feature)
    spec = fdir / "spec.md"

    if not spec.exists():
        die(f"diff-summary: spec.md not found: {spec}")

    try:
        spec_rel = str(spec.relative_to(resolved_root()))
    except ValueError:
        spec_rel = str(spec)

    old_ref = args.old
    new_ref = args.new or "HEAD"

    # Read spec.md at old revision
    old_text = _git_show_spec(resolved_root(), old_ref, spec_rel)

    # Read spec.md at new revision
    if new_ref in ("HEAD", "WORKING", "INDEX"):
        new_text = spec.read_text(encoding="utf-8")
    else:
        new_text = _git_show_spec(resolved_root(), new_ref, spec_rel)

    # Extract IDs and their anchor text
    old_ids = _extract_id_texts(old_text)
    new_ids = _extract_id_texts(new_text)

    old_set = set(old_ids.keys())
    new_set = set(new_ids.keys())

    added = sorted(new_set - old_set, key=_sort_spec_id)
    removed = sorted(old_set - new_set, key=_sort_spec_id)
    common = sorted(old_set & new_set, key=_sort_spec_id)

    # For common IDs, detect text changes and keyword changes
    changed = []
    for sid in common:
        old_line = old_ids[sid]
        new_line = new_ids[sid]

        if old_line != new_line:
            details = []

            old_must = bool(re.search(r"\bMUST\b", old_line, re.IGNORECASE))
            new_must = bool(re.search(r"\bMUST\b", new_line, re.IGNORECASE))
            old_should = bool(re.search(r"\bSHOULD\b", old_line, re.IGNORECASE))
            new_should = bool(re.search(r"\bSHOULD\b", new_line, re.IGNORECASE))

            if old_must and new_should and not new_must:
                details.append("weakened: MUST → SHOULD")
            elif old_should and new_must and not new_should:
                details.append("strengthened: SHOULD → MUST")

            if not details:
                details.append("text changed")

            changed.append({
                "id": sid,
                "details": details,
                "old": old_line[:200],
                "new": new_line[:200],
            })

    needs_regen = bool(added or removed or changed)
    approval_needed = bool(
        removed
        or any("weakened" in " ".join(c["details"]) for c in changed)
    )

    summary = {
        "feature": fdir.name,
        "old_ref": old_ref,
        "new_ref": new_ref,
        "added": [{"id": sid, "text": new_ids[sid][:200]} for sid in added],
        "removed": [{"id": sid, "text": old_ids[sid][:200]} for sid in removed],
        "changed": changed,
        "downstream_regeneration": {
            "plan_md": needs_regen,
            "tasks_md": needs_regen,
            "tests": needs_regen,
        },
        "requires_approval": approval_needed,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_diff_summary_markdown(summary)

# ── dispatch ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="traceability.py")
    parser.add_argument("-C", "--root", default=None, help="Path to the project root directory")
    parser.add_argument("--feature-dir", default=None, help="Explicit feature directory path")
    subparsers = parser.add_subparsers(dest="cmd")

    subparsers.add_parser("init", help="init <feature>")
    subparsers.add_parser("lint", help="lint <feature>")
    subparsers.add_parser("extract-spec-ids", help="extract-spec-ids <feature>")
    subparsers.add_parser("extract-trace", help="extract-trace <feature>")
    subparsers.add_parser("render", help="render <feature>")
    get_parser = subparsers.add_parser("get", help="get [--feature-dir FD] [feature] <mechanisms|spec-ids|trace>")
    get_parser.add_argument("positional_args", nargs="*")
    subparsers.add_parser("put-mechanisms", help="put-mechanisms <feature>")
    subparsers.add_parser("put-spec-ids", help="put-spec-ids <feature>")
    subparsers.add_parser("put-trace", help="put-trace <feature>")
    subparsers.add_parser("check-plan", help="check-plan <feature>")
    subparsers.add_parser("check-mechanisms", help="check-mechanisms <feature>")
    
    sum_parser = subparsers.add_parser("summarize-mechanisms", help="summarize-mechanisms [--json] <feature>")
    sum_parser.add_argument("--json", action="store_true")
    sum_parser.add_argument("feature", nargs="?")

    mc_parser = subparsers.add_parser("mark-consumed", help="mark-consumed --report <path>")
    mc_parser.add_argument("--report", required=True, help="Path to the gate report file to mark as consumed")

    diff_parser = subparsers.add_parser("diff-summary", help="diff-summary --old <ref> [--new <ref>] [--json] <feature>")
    diff_parser.add_argument("--old", required=True, help="Git ref for old version")
    diff_parser.add_argument("--new", default="HEAD", help="Git ref for new version (default: HEAD = working tree)")
    diff_parser.add_argument("--json", action="store_true")
    diff_parser.add_argument("feature", nargs="?")

    val_parser = subparsers.add_parser("validate", help="validate [--json] [--stage] <feature>")
    val_parser.add_argument("--json", action="store_true")
    val_parser.add_argument("--stage", choices=["spec", "plan", "tasks"])
    val_parser.add_argument("feature", nargs="?")

    vfm_parser = subparsers.add_parser("validate-frontmatter", help="validate-frontmatter <type> <file> [--json]")
    vfm_parser.add_argument("--json", action="store_true")
    vfm_parser.add_argument("artifact_type", nargs="?")
    vfm_parser.add_argument("file", nargs="?")

    args, remaining = parser.parse_known_args()

    global _ROOT, _FEATURE_DIR_OVERRIDE

    if args.root:
        _ROOT = Path(args.root).resolve()
    elif os.environ.get("ORDERSPEC_ROOT"):
        _ROOT = Path(os.environ["ORDERSPEC_ROOT"]).resolve()
    else:
        # Prefer current working directory if it looks like an OrderSpec project.
        # This handles cases where .orderspec is symlinked from another repo.
        cwd = Path.cwd()
        if (cwd / ".orderspec").is_dir():
            _ROOT = cwd
        else:
            _ROOT = script_dir().parent.parent

    if args.feature_dir:
        _FEATURE_DIR_OVERRIDE = args.feature_dir

    cmd = args.cmd

    if cmd == "init":
        cmd_init(remaining[0] if remaining else "")
    elif cmd == "lint":
        cmd_lint(remaining[0] if remaining else "")
    elif cmd == "extract-spec-ids":
        cmd_extract_spec_ids(remaining[0] if remaining else "")
    elif cmd == "extract-trace":
        cmd_extract_trace(remaining[0] if remaining else "")
    elif cmd == "render":
        cmd_render(remaining[0] if remaining else "")
    elif cmd == "get":
        if len(args.positional_args) == 1:
            # Only 'which' provided, feature is empty (relies on --feature-dir)
            cmd_get("", args.positional_args[0])
        elif len(args.positional_args) == 2:
            cmd_get(args.positional_args[0], args.positional_args[1])
        else:
            die("usage: traceability.py get [--feature-dir FD] [feature] <mechanisms|spec-ids|trace>", 64)
    elif cmd == "put-mechanisms":
        cmd_put_mechanisms(remaining[0] if remaining else "")
    elif cmd == "put-spec-ids":
        cmd_put_spec_ids(remaining[0] if remaining else "")
    elif cmd == "put-trace":
        cmd_put_trace(remaining[0] if remaining else "")
    elif cmd == "check-plan":
        cmd_check_plan(remaining[0] if remaining else "")
    elif cmd == "check-mechanisms":
        cmd_check_mechanisms(remaining[0] if remaining else "")
    elif cmd == "summarize-mechanisms":
        cmd_summarize_mechanisms(args.feature, json_out=args.json)
    elif cmd == "mark-consumed":
        cmd_mark_consumed(args)
    elif cmd == "diff-summary":
        cmd_diff_summary(args)
    elif cmd == "validate":
        cmd_validate(args)
    elif cmd == "validate-frontmatter":
        _frontmatter_cmd(args, remaining)
    else:
        parser.print_help()
        sys.exit(64)


if __name__ == "__main__":
    main()