#!/usr/bin/env python3
"""trace_lint.py — lint engines for traceability TSV files."""

from pathlib import Path

from trace_constants import (
    SPEC_PREFIXES, REQUIRED_MECHANISM_PREFIXES, FORBIDDEN_MECHANISM_PREFIXES,
    _PATH_RE, _SPEC_ID_RE, _TASK_ID_RE,
)
from trace_tsv import _read_table


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
