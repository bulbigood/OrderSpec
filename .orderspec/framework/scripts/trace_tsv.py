#!/usr/bin/env python3
"""trace_tsv.py — TSV read/write operations for traceability state files."""

import os
import shutil
import sys
from pathlib import Path

from trace_constants import (
    MECH_COLNAMES, MECH_MARKER,
    TRACE_COLNAMES, TRACE_MARKER,
    SPECIDS_COLNAMES, SPECIDS_MARKER,
    TAB,
)


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


def _lint_coverage(tracef, mtsv):
    from trace_lint import lint_file
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
