#!/usr/bin/env python3
"""traceability.py — deterministic source of truth for spec→task traceability.

Portable: Python 3 standard library only. No external dependencies.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = "v1"
TAB = "\t"

# Feature state directory name.
# IMPORTANT: must NOT be ".orderspec" — that collides with the repo-level
# .orderspec/ directory and breaks find_orderspec_root() in common.py.
FEATURE_STATE_DIRNAME = ".specify-state"

MECH_MARKER = "#orderspec mechanisms v1"
MECH_COLNAMES = f"spec_id{TAB}coverage_kind{TAB}mechanism{TAB}primary_files{TAB}test_type"

TRACE_MARKER = "#orderspec traceability v1"
TRACE_COLNAMES = f"spec_id{TAB}task_ids{TAB}files{TAB}source"

SPECIDS_MARKER = "#orderspec spec-ids v1"
SPECIDS_COLNAMES = f"spec_id{TAB}kind{TAB}section"

SPEC_PREFIXES = ["REQ", "NFR", "CON", "SC", "INV", "EDGE", "UJ", "AC", "Q", "ASM"]
# \s* allows extraction of IDs that are indented (e.g., nested ACs under UJs)
SPEC_PREFIX_RE = re.compile(r"^\s*- \*\*(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})\*\*")

ID_RE = re.compile(r"\b(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})\b")

TASK_LINE_RE = re.compile(r"^- \[[ xX]\] T(\d{3})")

# Narrowed Covers regex: matches lines starting with **Covers** or Covers
# (case-insensitive), to avoid false positives from prose containing "covers".
COVERS_RE = re.compile(r"^\s*\*{0,2}Covers?\*{0,2}\s*:", re.IGNORECASE)

SECTION_MAP = {
    "REQ": "functional", "NFR": "non-functional", "CON": "constraints",
    "SC": "success-criteria", "INV": "invariants", "EDGE": "edge-cases",
    "UJ": "user-journeys", "AC": "acceptance", "Q": "open-questions",
    "ASM": "assumptions",
}

# Default root is two levels up from the script, but can be overridden via -C or ENV
_ROOT = Path(__file__).resolve().parent.parent

def die(msg, rc=2):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(rc)

def script_dir():
    return Path(__file__).resolve().parent

def resolved_root():
    return _ROOT

def feature_dir(feature):
    return resolved_root() / "specs" / feature

def state_dir(feature):
    return feature_dir(feature) / FEATURE_STATE_DIRNAME


# ── TSV helpers ─────────────────────────────────────────────────────────────

def _read_tsv_lines(path):
    """Read raw lines with strict LF validation. Raises ValueError on CRLF or blank data lines."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = f.readlines()
    for i, line in enumerate(lines, start=1):
        if "\r" in line:
            raise ValueError(f"CRLF line ending at line {i}")
        if i > 2 and line.rstrip("\n") == "":
            raise ValueError(f"blank data line at line {i}")
    return lines


def _tsv_lines_to_rows(lines):
    """Convert validated TSV lines (skip marker+header) to list of dicts."""
    rows = []
    if len(lines) < 2:
        return rows
    colnames = lines[1].rstrip("\n").split(TAB)
    for line in lines[2:]:
        line = line.rstrip("\n")
        if not line:
            continue
        parts = line.split(TAB)
        rows.append(dict(zip(colnames, parts)))
    return rows


def read_tsv_body(path):
    """Read TSV file, skip marker + header, return list of dicts.
    Raises ValueError on CRLF or blank data lines."""
    lines = _read_tsv_lines(path)
    return _tsv_lines_to_rows(lines)


def write_tsv_atomic(path, marker, colnames, rows):
    """Write TSV atomically via temp file. rows is list of lists/tuples."""
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(marker + "\n")
        f.write(colnames + "\n")
        for row in rows:
            f.write(TAB.join(str(c) for c in row) + "\n")
    shutil.move(str(tmp), str(path))


# ── lint engine ─────────────────────────────────────────────────────────────

def lint_mechanisms(rows):
    errors = []
    seen_ids = set()
    valid_ck = {"direct", "documented"}
    valid_tt = {"unit", "integration", "documented"}
    for i, row in enumerate(rows, start=3):
        spec_id = row.get("spec_id", "")
        ck = row.get("coverage_kind", "")
        mech = row.get("mechanism", "")
        files = row.get("primary_files", "")
        tt = row.get("test_type", "")

        if not spec_id:
            errors.append(f"ERROR {i}: empty spec_id")
            continue
        if not re.match(r"^(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})$", spec_id):
            errors.append(f"ERROR {i}: bad spec_id \"{spec_id}\"")
            continue
        if spec_id in seen_ids:
            errors.append(f"ERROR {i}: duplicate spec_id \"{spec_id}\"")
            continue
        seen_ids.add(spec_id)

        if not mech:
            errors.append(f"ERROR {i}: empty mechanism for \"{spec_id}\"")

        if ck not in valid_ck and not ck.startswith("delegated:"):
            errors.append(f"ERROR {i}: bad coverage_kind \"{ck}\" for \"{spec_id}\"")
            continue

        if tt not in valid_tt:
            errors.append(f"ERROR {i}: bad test_type \"{tt}\" for \"{spec_id}\"")

        if ck == "direct" and tt not in {"unit", "integration"}:
            errors.append(
                f"ERROR {i}: coverage_kind=direct requires test_type unit|integration (got \"{tt}\") for \"{spec_id}\""
            )
        elif ck == "documented" and tt != "documented":
            errors.append(
                f"ERROR {i}: coverage_kind=documented requires test_type=documented (got \"{tt}\") for \"{spec_id}\""
            )
        elif tt == "documented" and ck != "documented":
            errors.append(
                f"ERROR {i}: test_type=documented requires coverage_kind=documented (got \"{ck}\") for \"{spec_id}\""
            )
        elif ck.startswith("delegated:"):
            tgt = ck[len("delegated:") :]
            if tgt == spec_id:
                errors.append(f"ERROR {i}: delegated coverage points to itself for \"{spec_id}\"")
            if not re.match(r"^(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})$", tgt):
                errors.append(f"ERROR {i}: bad delegated target \"{tgt}\" for \"{spec_id}\"")

        if not files:
            errors.append(f"ERROR {i}: empty primary_files for \"{spec_id}\"")
        else:
            for p in files.split(";"):
                if not p:
                    errors.append(f"ERROR {i}: empty path token in primary_files for \"{spec_id}\"")
                elif " " in p or not re.match(r"^[A-Za-z0-9._/-]+$", p):
                    errors.append(f"ERROR {i}: bad path token \"{p}\" for \"{spec_id}\"")

    return errors


def lint_trace(rows):
    errors = []
    seen_ids = set()
    task_re = re.compile(r"^T\d{3}$")
    path_re = re.compile(r"^[A-Za-z0-9._/-]+$")
    for i, row in enumerate(rows, start=3):
        spec_id = row.get("spec_id", "")
        tasks = row.get("task_ids", "")
        files = row.get("files", "")
        source = row.get("source", "")

        if not spec_id:
            errors.append(f"ERROR {i}: empty spec_id")
            continue
        if not re.match(r"^(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})$", spec_id):
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
                if not task_re.match(t):
                    errors.append(f"ERROR {i}: bad task_id \"{t}\" for \"{spec_id}\"")
        elif source == "tasks.md":
            errors.append(f"ERROR {i}: empty task_ids but source=tasks.md for \"{spec_id}\"")

        if files:
            for p in files.split(";"):
                if p and not path_re.match(p):
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
        if not re.match(r"^(" + "|".join(SPEC_PREFIXES) + r")-(\d{3})$", spec_id):
            errors.append(f"ERROR {i}: bad spec_id \"{spec_id}\"")
            continue
        if spec_id in seen_ids:
            errors.append(f"ERROR {i}: duplicate spec_id \"{spec_id}\"")
            continue
        seen_ids.add(spec_id)

        if kind not in SPEC_PREFIXES:
            errors.append(f"ERROR {i}: bad kind \"{kind}\" for \"{spec_id}\"")
        else:
            prefix = spec_id.split("-")[0]
            if kind != prefix:
                errors.append(f"ERROR {i}: kind \"{kind}\" != id prefix \"{prefix}\"")

        if not section:
            errors.append(f"ERROR {i}: empty section for \"{spec_id}\"")
    return errors


def lint_file(path, kind):
    if not path.exists():
        return [f"FATAL: {path} not found"]
    try:
        lines = _read_tsv_lines(path)
    except ValueError as e:
        return [f"FATAL: {e}"]

    if len(lines) < 2:
        return [f"FATAL: {path} empty or missing header"]
    marker = lines[0].rstrip("\n")
    header = lines[1].rstrip("\n")
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
    if marker != expected_marker:
        return [f"FATAL: {kind} wrong version marker"]
    if header != expected_header:
        return [f"FATAL: {kind} wrong column names"]

    rows = _tsv_lines_to_rows(lines)

    if kind == "mechanisms":
        return lint_mechanisms(rows)
    elif kind == "trace":
        return lint_trace(rows)
    elif kind == "specids":
        return lint_specids(rows)
    return []


# ── commands ────────────────────────────────────────────────────────────────

def cmd_init(feature):
    if not feature:
        die("usage: traceability.py init <feature>", 64)
    fdir = feature_dir(feature)
    if not fdir.exists():
        die(f"feature dir not found: {fdir} (expected specs/{feature})")
    sdir = state_dir(feature)
    sdir.mkdir(parents=True, exist_ok=True)
    schema_file = sdir / ".schema"
    if schema_file.exists():
        sv = schema_file.read_text().strip()
        if sv != SCHEMA_VERSION:
            die(f".schema exists with version '{sv}', expected '{SCHEMA_VERSION}'")
        print(f"init: already initialized ({feature}, schema {sv})")
        return
    schema_file.write_text(SCHEMA_VERSION + "\n")
    print(f"init: created {sdir} (schema {SCHEMA_VERSION})")


def cmd_lint(feature):
    if not feature:
        die("usage: traceability.py lint <feature>", 64)
    sdir = state_dir(feature)
    if not sdir.exists():
        die(f"state not initialized for '{feature}'; run: traceability.py init {feature}")
    schema_file = sdir / ".schema"
    if not schema_file.exists():
        die(f"missing {schema_file}; run: traceability.py init {feature}")
    sv = schema_file.read_text().strip()
    if sv != SCHEMA_VERSION:
        die(f".schema is '{sv}', expected '{SCHEMA_VERSION}'")

    rc = 0
    mech = sdir / "mechanisms.tsv"
    if not mech.exists():
        die(f"mechanisms.tsv not found: {mech}")
    errs = lint_file(mech, "mechanisms")
    if errs:
        rc = 2
        for e in errs:
            print(e, file=sys.stderr)

    specids = sdir / "spec-ids.tsv"
    if specids.exists():
        errs = lint_file(specids, "specids")
        if errs:
            rc = 2
            for e in errs:
                print(e, file=sys.stderr)

    trace = sdir / "traceability.tsv"
    if trace.exists():
        errs = lint_file(trace, "trace")
        if errs:
            rc = 2
            for e in errs:
                print(e, file=sys.stderr)

    if rc != 0:
        print(f"lint: FAIL for {feature}", file=sys.stderr)
        sys.exit(2)
    print(f"lint: OK ({feature})")


def cmd_put_mechanisms(feature):
    if not feature:
        die("usage: traceability.py put-mechanisms <feature>", 64)
    _put_via_lint(feature, "mechanisms", "mechanisms.tsv", MECH_MARKER, MECH_COLNAMES)


def cmd_put_spec_ids(feature):
    if not feature:
        die("usage: traceability.py put-spec-ids <feature>", 64)
    _put_via_lint(feature, "specids", "spec-ids.tsv", SPECIDS_MARKER, SPECIDS_COLNAMES)


def cmd_extract_spec_ids(feature):
    if not feature:
        die("usage: traceability.py extract-spec-ids <feature>", 64)
    fdir = feature_dir(feature)
    spec = fdir / "spec.md"
    if not spec.exists():
        die(f"spec.md not found: {spec}")
    sdir = state_dir(feature)
    if not sdir.exists():
        die(f"state not initialized for '{feature}'; run: traceability.py init {feature}")

    # ── Renumbering detection: read existing IDs before overwriting ──
    existing_tsv = sdir / "spec-ids.tsv"
    old_ids = set()
    if existing_tsv.exists():
        try:
            for row in read_tsv_body(existing_tsv):
                old_ids.add(row.get("spec_id", ""))
        except (ValueError, KeyError):
            pass  # ignore corrupt old TSV

    # ── Extract IDs from spec.md ──
    rows = []
    new_ids = set()
    with open(spec, "r", encoding="utf-8") as f:
        for line in f:
            m = SPEC_PREFIX_RE.match(line)
            if m:
                prefix = m.group(1)
                num = m.group(2)
                spec_id = f"{prefix}-{num}"
                section = SECTION_MAP.get(prefix, "unknown")
                rows.append([spec_id, prefix, section])
                new_ids.add(spec_id)

    # ── Warn about disappeared IDs (renumbering / silent removal) ──
    removed = old_ids - new_ids
    if removed:
        for sid in sorted(removed):
            print(
                f"WARNING: {sid} disappeared from spec.md — "
                f"verify it was tombstoned in §2 Out-of-Scope, not silently renumbered",
                file=sys.stderr,
            )

    _put_via_lint(feature, "specids", "spec-ids.tsv", SPECIDS_MARKER, SPECIDS_COLNAMES, rows)


def _put_via_lint(feature, kind, basename, marker, colnames, rows=None):
    fdir = feature_dir(feature)
    if not fdir.exists():
        die(f"feature dir not found: {fdir}")
    sdir = state_dir(feature)
    if not sdir.exists():
        die(f"state not initialized for '{feature}'; run: traceability.py init {feature}")
    target = sdir / basename
    if rows is None:
        rows = []
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            rows.append(line.split(TAB))
    tmp = target.with_suffix(f".tmp.{os.getpid()}")
    write_tsv_atomic(tmp, marker, colnames, rows)
    errs = lint_file(tmp, kind)
    if errs:
        tmp.unlink(missing_ok=True)
        for e in errs:
            print(e, file=sys.stderr)
        print(f"put-{basename}: rejected, {target} not modified", file=sys.stderr)
        sys.exit(2)
    shutil.move(str(tmp), str(target))
    print(f"put-{basename}: wrote {target}")


def cmd_extract_trace(feature):
    if not feature:
        die("usage: traceability.py extract-trace <feature>", 64)
    fdir = feature_dir(feature)
    tasks = fdir / "tasks.md"
    if not tasks.exists():
        die(f"tasks.md not found: {tasks}")
    sdir = state_dir(feature)
    if not sdir.exists():
        die(f"state not initialized for '{feature}'; run: traceability.py init {feature}")
    mtsv = sdir / "mechanisms.tsv"
    if not mtsv.exists():
        die(f"extract-trace: mechanisms.tsv not found: {mtsv} (run put-mechanisms first)")

    # Load mechanisms
    mech_rows = read_tsv_body(mtsv)
    ck_of = {}
    pf_of = {}
    bind = {}  # (path, spec_id) -> True for direct mechanisms
    for row in mech_rows:
        sid = row["spec_id"]
        ck = row["coverage_kind"]
        files = row["primary_files"]
        ck_of[sid] = ck
        pf_of[sid] = files
        if ck == "direct":
            for p in files.split(";"):
                if p:
                    bind[(p, sid)] = True

    # Parse tasks.md
    task_re = re.compile(r"^- \[[ xX]\] T(\d{3})")
    bug = False
    trace_rows = {}  # spec_id -> {"tasks": set(), "files": set(), "source": "tasks.md"}
    seen_ref = set()

    with open(tasks, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = task_re.match(line)
            if not m:
                continue
            tid = f"T{m.group(1)}"
            parts = line.split(" | ")
            if len(parts) < 3:
                continue

            path = parts[1].strip()

            if len(parts) == 3:
                refs_str = ""
            else:
                refs_str = parts[2].strip()

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
                if not ID_RE.match(rid):
                    print(f"extract-trace: bad ref id {rid} in {tid}", file=sys.stderr)
                    bug = True
                    continue
                if (rid, tid) in seen_ref:
                    print(f"extract-trace: duplicate ref {rid} within {tid}", file=sys.stderr)
                    bug = True
                    continue
                seen_ref.add((rid, tid))

                if rid not in ck_of:
                    print(
                        f"extract-trace: ref {rid} in {tid} is not a known mechanism",
                        file=sys.stderr,
                    )
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
                        f"extract-trace: ref {rid} in {tid} is delegated; task its delegate, not the AC id",
                        file=sys.stderr,
                    )
                    bug = True
                    continue
                if (path, rid) not in bind:
                    print(
                        f"extract-trace: ref {rid} on {tid} not in its primary_files (path={path}); filler/mis-attributed ref",
                        file=sys.stderr,
                    )
                    bug = True
                    continue

                if rid not in trace_rows:
                    trace_rows[rid] = {"tasks": set(), "files": set(), "source": "tasks.md"}
                trace_rows[rid]["tasks"].add(tid)
                trace_rows[rid]["files"].add(path)

    if bug:
        sys.exit(3)

    # Add documented mechanisms as plan.md rows
    for sid, ck in ck_of.items():
        if ck == "documented" and sid not in trace_rows:
            trace_rows[sid] = {
                "tasks": set(),
                "files": set(pf_of.get(sid, "").split(";") if pf_of.get(sid, "") else []),
                "source": "plan.md",
            }

    # Sort by spec_id
    out_rows = []
    for sid in sorted(trace_rows.keys(), key=lambda x: (x.split("-")[0], int(x.split("-")[1]))):
        r = trace_rows[sid]
        out_rows.append(
            [
                sid,
                ";".join(sorted(r["tasks"])),
                ";".join(sorted(f for f in r["files"] if f)),
                r["source"],
            ]
        )

    # Coverage lint before writing
    mtsv = sdir / "mechanisms.tsv"
    tmp = (sdir / "traceability.tsv").with_suffix(f".tmp.{os.getpid()}")
    write_tsv_atomic(tmp, TRACE_MARKER, TRACE_COLNAMES, out_rows)
    errs = lint_file(tmp, "trace")
    if errs:
        tmp.unlink(missing_ok=True)
        for e in errs:
            print(e, file=sys.stderr)
        print("extract-trace: rejected (format), traceability.tsv not modified", file=sys.stderr)
        sys.exit(2)
    if mtsv.exists():
        cov_errs = _lint_coverage(tmp, mtsv)
        if cov_errs:
            tmp.unlink(missing_ok=True)
            for e in cov_errs:
                print(e, file=sys.stderr)
            print(
                "extract-trace: rejected (coverage), traceability.tsv not modified",
                file=sys.stderr,
            )
            sys.exit(2)
    shutil.move(str(tmp), str(sdir / "traceability.tsv"))
    print(f"extract-trace: wrote {sdir / 'traceability.tsv'}")


def cmd_put_trace(feature):
    if not feature:
        die("usage: traceability.py put-trace <feature>", 64)
    sdir = state_dir(feature)
    if not sdir.exists():
        die(f"state not initialized for '{feature}'; run: traceability.py init {feature}")
    target = sdir / "traceability.tsv"
    mtsv = sdir / "mechanisms.tsv"
    rows = []
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line:
            continue
        rows.append(line.split(TAB))
    tmp = target.with_suffix(f".tmp.{os.getpid()}")
    write_tsv_atomic(tmp, TRACE_MARKER, TRACE_COLNAMES, rows)
    errs = lint_file(tmp, "trace")
    if errs:
        tmp.unlink(missing_ok=True)
        for e in errs:
            print(e, file=sys.stderr)
        print(f"put-trace: rejected (format), {target} not modified", file=sys.stderr)
        sys.exit(2)
    if mtsv.exists():
        cov_errs = _lint_coverage(tmp, mtsv)
        if cov_errs:
            tmp.unlink(missing_ok=True)
            for e in cov_errs:
                print(e, file=sys.stderr)
            print(f"put-trace: rejected (coverage), {target} not modified", file=sys.stderr)
            sys.exit(2)
    shutil.move(str(tmp), str(target))
    print(f"put-trace: wrote {target}")


def _lint_coverage(tracef, mtsv):
    errors = []
    mech_rows = read_tsv_body(mtsv)
    trace_rows = read_tsv_body(tracef)
    mech = {}
    deleg = {}
    taskcov = {}
    plancov = {}
    for row in mech_rows:
        sid = row["spec_id"]
        ck = row["coverage_kind"]
        mech[sid] = ck
        if ck.startswith("delegated:"):
            deleg[sid] = ck[len("delegated:") :]
    for row in trace_rows:
        sid = row["spec_id"]
        src = row["source"]
        if src == "tasks.md":
            taskcov[sid] = True
        if src == "plan.md":
            plancov[sid] = True

    for sid, ck in mech.items():
        if ck == "direct":
            tgt = deleg.get(sid, sid)
            if tgt not in taskcov:
                errors.append(f"coverage: direct {sid} uncovered (via {tgt})")
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


def cmd_get(feature, which):
    if not feature or not which:
        die("usage: traceability.py get <feature> <mechanisms|spec-ids|trace>", 64)
    mapping = {
        "mechanisms": ("mechanisms.tsv", MECH_MARKER),
        "spec-ids": ("spec-ids.tsv", SPECIDS_MARKER),
        "trace": ("traceability.tsv", TRACE_MARKER),
    }
    if which not in mapping:
        die(f"get: unknown which '{which}' (want mechanisms|spec-ids|trace)", 64)
    basename, marker = mapping[which]
    sdir = state_dir(feature)
    target = sdir / basename
    if not target.exists():
        die(f"get: no {basename} for feature '{feature}' (run extract/put first)")
    if which == "trace":
        if _trace_stale(feature):
            die(
                f"get: traceability.tsv is stale (tasks.md changed/removed); run: traceability.py extract-trace {feature}"
            )
    with open(target, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) < 2 or lines[0].rstrip("\n") != marker:
        die(f"get: {basename}: wrong/missing contract marker on line 1")
    for line in lines[2:]:
        sys.stdout.write(line)


def _trace_stale(feature):
    fdir = feature_dir(feature)
    sdir = state_dir(feature)
    tasks = fdir / "tasks.md"
    trace = sdir / "traceability.tsv"
    if not trace.exists():
        return False
    if not tasks.exists():
        print("stale: tasks.md is gone but traceability.tsv remains", file=sys.stderr)
        return True
    if tasks.stat().st_mtime > trace.stat().st_mtime:
        print("stale: tasks.md is newer than traceability.tsv", file=sys.stderr)
        return True
    return False


def cmd_render(feature):
    if not feature:
        die("usage: traceability.py render <feature>", 64)
    sdir = state_dir(feature)
    if not sdir.exists():
        die(f"state not initialized for '{feature}'; run: traceability.py init {feature}")
    tracef = sdir / "traceability.tsv"
    mtsv = sdir / "mechanisms.tsv"
    if not tracef.exists():
        die(f"render: no traceability.tsv for '{feature}'; run: traceability.py extract-trace {feature}")
    if _trace_stale(feature):
        print("render: traceability.tsv is stale, not rendering", file=sys.stderr)
        sys.exit(2)
    errs = lint_file(tracef, "trace")
    if errs:
        print("render: traceability.tsv failed lint, not rendering", file=sys.stderr)
        sys.exit(2)
    if mtsv.exists():
        errs = lint_file(mtsv, "mechanisms")
        if errs:
            print("render: mechanisms.tsv failed lint, not rendering", file=sys.stderr)
            sys.exit(2)

    kind_of = {}
    if mtsv.exists():
        for row in read_tsv_body(mtsv):
            kind_of[row["spec_id"]] = row["coverage_kind"]

    trace_rows = read_tsv_body(tracef)
    lines = [
        "<!-- DO NOT EDIT — generated by traceability.py render from .specify-state/*.tsv -->"
    ]
    lines.append(f"# Traceability — {feature}\n")
    lines.append("| spec_id | kind | tasks | files | source |")
    lines.append("|---------|------|-------|-------|--------|")
    counts = {"direct": 0, "documented": 0, "delegated": 0, "total": 0}
    for row in trace_rows:
        sid = row["spec_id"]
        k = kind_of.get(sid, "?")
        tasks = row["task_ids"] or "—"
        files = row["files"] or "—"
        source = row["source"]
        tasks = tasks.replace("|", "\\|")
        files = files.replace("|", "\\|")
        lines.append(f"| {sid} | {k} | {tasks} | {files} | {source} |")
        counts["total"] += 1
        if k == "direct":
            counts["direct"] += 1
        elif k == "documented":
            counts["documented"] += 1
        elif k.startswith("delegated:"):
            counts["delegated"] += 1

    summary = f"\n{counts['total']} mechanisms · {counts['direct']} direct · {counts['documented']} documented · {counts['delegated']} delegated\n"
    lines.append(summary)
    target = sdir / "traceability.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"render: wrote {target}")


# ── check-plan ──────────────────────────────────────────────────────────────

def cmd_check_plan(feature):
    if not feature:
        die("usage: traceability.py check-plan <feature>", 64)
    fdir = feature_dir(feature)
    plan = fdir / "plan.md"
    if not plan.exists():
        die(f"check-plan: plan.md not found: {plan}")

    rc = 0
    manifest = _extract_pathmanifest(plan)
    if not manifest:
        print("check-plan: ERROR — no pathmanifest block in plan.md", file=sys.stderr)
        sys.exit(1)

    for line in manifest:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        parts = line.split()
        if not parts:
            continue
        path = parts[0]
        tag = ""
        if "[NEW]" in line:
            tag = "[NEW]"
        elif "[MOD]" in line:
            tag = "[MOD]"

        if path.endswith("/"):
            print(f"check-plan: ERROR — directory in manifest: {path}", file=sys.stderr)
            rc = 1
            continue

        if not tag:
            print(f"check-plan: ERROR — missing [NEW]/[MOD] tag: {path}", file=sys.stderr)
            rc = 1
            continue

        full_path = resolved_root() / path
        if tag == "[MOD]" and not full_path.exists():
            print(f"check-plan: ERROR — [MOD] path does not exist: {path}", file=sys.stderr)
            rc = 1
        elif tag == "[NEW]" and full_path.exists():
            print(f"check-plan: ERROR — [NEW] path already exists: {path}", file=sys.stderr)
            rc = 1

    if rc == 0:
        print(f"check-plan: OK ({feature})")
    else:
        print(f"check-plan: FAIL ({feature}) — see errors above", file=sys.stderr)
    sys.exit(rc)


def _extract_pathmanifest(plan_path):
    result = []
    in_block = False
    with open(plan_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if re.match(r"^\s*```\s*pathmanifest", line):
                in_block = True
                continue
            if in_block and re.match(r"^\s*```\s*$", line):
                break
            if in_block:
                result.append(line)
    return result


# ── validate (cross-artifact) ───────────────────────────────────────────────

def _extract_section(text, header_prefix):
    """Extracts markdown section content by header prefix (e.g., '## 9.').
    Returns text from the header line up to (but not including) the next
    header of the same or higher level."""
    lines = text.splitlines()
    start_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(header_prefix):
            start_idx = i
            break
    if start_idx == -1:
        return ""
    
    level = len(lines[start_idx]) - len(lines[start_idx].lstrip('#'))
    end_idx = len(lines)
    
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].lstrip()
        if stripped.startswith('#') and not stripped.startswith('#' * (level + 1)):
            # Check if it's a header of same or higher level
            this_level = len(lines[i]) - len(lines[i].lstrip('#'))
            if this_level <= level:
                end_idx = i
                break
    
    return "\n".join(lines[start_idx:end_idx])


def _extract_subsection(text, header_prefix):
    """Extracts a subsection (###) from within a larger section.
    Returns text from the header line up to the next ### or ## header."""
    lines = text.splitlines()
    start_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(header_prefix):
            start_idx = i
            break
    if start_idx == -1:
        return ""
    
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].lstrip()
        # Stop at next ### or ## header
        if stripped.startswith('## ') or stripped.startswith('### '):
            end_idx = i
            break
    
    return "\n".join(lines[start_idx:end_idx])


def _extract_endpoint_blocks(section_9_text):
    """Extracts endpoint blocks from §9 API Contracts.
    Returns list of dicts: {method, path, block_text}
    Each block starts with '- **METHOD** `path`' and ends at the next endpoint or section."""
    lines = section_9_text.splitlines()
    endpoints = []
    current_start = -1
    current_method = ""
    current_path = ""
    
    for i, line in enumerate(lines):
        m = re.match(r"-\s\*\*(GET|POST|PATCH|PUT|DELETE)\*\*\s`([^`]+)`", line)
        if m:
            if current_start != -1:
                endpoints.append({
                    "method": current_method,
                    "path": current_path,
                    "block_text": "\n".join(lines[current_start:i])
                })
            current_start = i
            current_method = m.group(1)
            current_path = m.group(2)
    
    if current_start != -1:
        endpoints.append({
            "method": current_method,
            "path": current_path,
            "block_text": "\n".join(lines[current_start:])
        })
    
    return endpoints


def _extract_status_codes_contextual(text):
    """Extracts 3-digit numbers that appear to be HTTP status codes
    by checking surrounding context for HTTP-related keywords.
    Returns set of status code strings."""
    lines = text.splitlines()
    statuses = set()
    http_keywords = ["status", "response", "returns", "return", "http", 
                      "bad request", "not found", "gone", "error", "forbidden",
                      "unauthorized", "server error", "success", "created"]
    
    for i, line in enumerate(lines):
        # Look for 3-digit numbers in the line
        numbers = re.findall(r"\b([1-5]\d{2})\b", line)
        if not numbers:
            continue
        
        # Check if line or nearby lines contain HTTP context
        context_lines = line.lower()
        if i > 0:
            context_lines = lines[i-1].lower() + " " + context_lines
        if i < len(lines) - 1:
            context_lines = context_lines + " " + lines[i+1].lower()
        
        for num in numbers:
            # Accept if it's in valid HTTP range and has context
            if num in {"200", "201", "202", "204", "400", "401", "403", 
                        "404", "409", "410", "422", "500", "503"}:
                if any(kw in context_lines for kw in http_keywords):
                    statuses.add(num)
    
    return statuses

def cmd_validate(args):
    feature = args.feature
    if not feature:
        die("usage: traceability.py validate [--json] [--stage spec|plan|tasks] <feature>", 64)

    fdir = feature_dir(feature)
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

    need_plan = stage in {"plan", "tasks"}
    need_tasks = stage == "tasks"

    if need_plan and not have_plan:
        die(f"validate: stage={stage} requires plan.md (missing: {plan})", 2)
    if need_tasks and not have_tasks:
        die(f"validate: stage={stage} requires tasks.md (missing: {tasks})", 2)

    findings = []

    def add(check, severity, location, message):
        findings.append({"check": check, "severity": severity, "location": location, "message": message})

    # Read spec IDs
    spec_text = spec.read_text(encoding="utf-8")
    spec_ids = set(ID_RE.findall(spec_text))
    spec_ids = set(f"{m[0]}-{m[1]}" for m in spec_ids)

    spec_req = [sid for sid in spec_ids if sid.startswith("REQ-")]
    spec_ac = [sid for sid in spec_ids if sid.startswith("AC-")]
    spec_edge = [sid for sid in spec_ids if sid.startswith("EDGE-")]
    spec_inv = [sid for sid in spec_ids if sid.startswith("INV-")]
    spec_uj = [sid for sid in spec_ids if sid.startswith("UJ-")]

    # Read mechanisms for coverage-kind aware checks (M2/M3)
    ck_of = {}
    sdir = state_dir(feature)
    mtsv = sdir / "mechanisms.tsv"
    if mtsv.exists():
        for row in read_tsv_body(mtsv):
            ck_of[row["spec_id"]] = row.get("coverage_kind", "")

    # M1: REQ -> UJ Covers (narrowed regex: only lines starting with **Covers** or Covers)
    covers_ids = set()
    for line in spec_text.splitlines():
        if COVERS_RE.match(line):
            for m in ID_RE.findall(line):
                covers_ids.add(f"{m[0]}-{m[1]}")
    for sid in spec_req:
        if sid not in covers_ids:
            add("M1", "HIGH", "spec.md", f"{sid} is not listed in any UJ 'Covers'")

    # M6: unresolved markers
    for i, line in enumerate(spec_text.splitlines(), start=1):
        if re.search(r"\bQ-\d+\b|\[NEEDS CLARIFICATION", line):
            add("M6", "HIGH", f"spec.md:{i}", f"Unresolved clarification: {line.strip()}")

    # ── Mechanical-Semantic Checks (M15-M17) ──────────────────────────────
    # These checks are conservative: high-confidence findings only.
    # The LLM semantic passes handle anything the script cannot determine.
    
    section_9 = _extract_section(spec_text, "## 9.")
    section_11 = _extract_section(spec_text, "## 11.")
    section_12 = _extract_section(spec_text, "## 12.")
    
    # ── M15a: Global missing status codes ──
    # If a status code appears in §11/§12 in HTTP context but is entirely
    # absent from §9, that's a high-confidence finding.
    if section_9 and (section_11 or section_12):
        statuses_in_9 = _extract_status_codes_contextual(section_9)
        statuses_in_11_12 = _extract_status_codes_contextual(section_11 + "\n" + section_12)
        
        for st in statuses_in_11_12:
            if st not in statuses_in_9:
                add("M15a", "MEDIUM", "spec.md", 
                    f"Status code {st} used in §11/§12 but not declared anywhere in §9 API Contracts")
    
    # ── M15b: Endpoint-specific status mismatch ──
    if section_9 and section_12:
        endpoint_blocks = _extract_endpoint_blocks(section_9)
        
        # Build map: (method, path_substring) -> set of statuses in that block
        endpoint_statuses = {}
        for ep in endpoint_blocks:
            ep_statuses = _extract_status_codes_contextual(ep["block_text"])
            # Normalize path for matching (remove /api/v1 prefix, params)
            norm_path = ep["path"].replace("/api/v1", "").lower()
            endpoint_statuses[(ep["method"], norm_path)] = ep_statuses
        
        # Scan §12 for lines that mention both an endpoint and a status
        ac_lines = section_12.splitlines()
        for line in ac_lines:
            # Look for endpoint references in AC lines
            for ep_key, ep_sts in endpoint_statuses.items():
                method, path = ep_key
                # Check if this AC line references this endpoint AND method
                # Simple heuristic: path appears in the line AND method appears in the line
                path_clean = path.replace(":id", "").replace("/", "").strip(":")
                method_lower = method.lower()
                
                if path_clean and len(path_clean) > 3 and path_clean in line.lower() and method_lower in line.lower():
                    line_statuses = _extract_status_codes_contextual(line)
                    for st in line_statuses:
                        if st not in ep_sts:
                            add("M15b", "MEDIUM", "spec.md:§12",
                                f"AC references status {st} for endpoint {method} {path} but it is not in §9 contract for that endpoint")
    
    # ── M16: Authorization coverage ──
    # If §9 has an Authorization subsection, verify it covers all endpoints.
    # We extract ONLY the Authorization subsection (not everything after it).
    if section_9:
        auth_subsection = _extract_subsection(section_9, "### Authorization")
        if auth_subsection:
            # Check if auth text mentions all endpoints or read endpoints explicitly
            auth_lower = auth_subsection.lower()
            has_mutable_only = any(kw in auth_lower for kw in ["mutating", "mutation", "post", "patch", "delete"])
            has_get_coverage = any(kw in auth_lower for kw in ["get", "read", "public", "all endpoints", "all routes", "every endpoint"])
            has_explicit_get_policy = "get" in auth_lower or "read" in auth_lower or "public" in auth_lower
            
            # Extract endpoints from §9
            all_endpoints = re.findall(r"-\s\*\*(GET|POST|PATCH|PUT|DELETE)\*\*\s`([^`]+)`", section_9)
            has_get = any(e[0] == "GET" for e in all_endpoints)
            
            if has_get and has_mutable_only and not has_explicit_get_policy and not has_get_coverage:
                add("M16", "MEDIUM", "spec.md:§9",
                    "Authorization subsection covers mutating endpoints but does not mention GET/read endpoints")
    
    # ── M17: AC field alignment (conservative) ──
    # Only check fields that appear in backticks in AC lines that also
    # mention "contains", "including", "with", "returned with".
    # Severity is LOW to avoid false positives blocking the pipeline.
    if section_9 and section_12:
        # Extract all field-like tokens from §9 schemas
        fields_in_9 = set()
        # Match patterns like: "field": type  or  "field": "value"
        for m in re.finditer(r'"?(\w+)"?\s*:\s', section_9):
            fields_in_9.add(m.group(1))
        
        # Scan AC for field references in backticks
        ac_field_patterns = [
            r"contains?\s+`(\w+)`",
            r"including\s+`(\w+)`",
            r"with\s+`(\w+)`",
            r"returned.*`(\w+)`",
            r"includes?\s+`(\w+)`",
            r"`(\w+)`\s+field",
        ]
        
        ac_fields = set()
        for line in section_12.splitlines():
            for pattern in ac_field_patterns:
                for m in re.finditer(pattern, line, re.IGNORECASE):
                    ac_fields.add(m.group(1))
        
        # Common envelope fields that are not part of entity schemas
        envelope_fields = {"results", "page", "limit", "totalPages", "totalResults", "total"}
        
        for f in ac_fields:
            if f not in fields_in_9 and f not in envelope_fields and f.lower() not in {x.lower() for x in fields_in_9}:
                add("M17", "LOW", "spec.md:§12",
                    f"AC checks field '{f}' but it is not found in §9 API Contracts schemas")
    
    # PLAN-STAGE
    if need_plan:
        plan_text = plan.read_text(encoding="utf-8")
        plan_refs = set(ID_RE.findall(plan_text))
        plan_refs = set(f"{m[0]}-{m[1]}" for m in plan_refs)

        # M5 plan side
        for sid in plan_refs:
            if sid not in spec_ids:
                add("M5", "HIGH", "plan.md", f"{sid} cited in plan.md but not defined in spec.md")

        # M9 + M10: path manifest
        manifest = _extract_pathmanifest(plan)
        if not manifest:
            add("M9", "HIGH", "plan.md", "No pathmanifest block found")
        else:
            for line in manifest:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("<!--"):
                    continue
                parts = line.split()
                if not parts:
                    continue
                path = parts[0]
                tag = ""
                if "[NEW]" in line:
                    tag = "[NEW]"
                elif "[MOD]" in line:
                    tag = "[MOD]"

                if path.endswith("/"):
                    add("M9", "MEDIUM", "plan.md", f"Manifest lists directory: {path}")
                    continue
                if not tag:
                    add("M9", "MEDIUM", "plan.md", f"Missing [NEW]/[MOD] tag: {path}")
                elif tag == "[MOD]" and not (resolved_root() / path).exists():
                    add("M10", "HIGH", "plan.md", f"[MOD] path '{path}' does not exist in repo")
                elif tag == "[NEW]" and (resolved_root() / path).exists():
                    add("M10", "HIGH", "plan.md", f"[NEW] path '{path}' already exists in repo")

    # TASKS-STAGE
    if need_tasks:
        tasks_text = tasks.read_text(encoding="utf-8")
        task_lines = []
        for i, line in enumerate(tasks_text.splitlines(), start=1):
            if TASK_LINE_RE.match(line):
                task_lines.append((i, line))

        # Collect refs ONLY from field 3 of task lines
        task_refs = set()
        for line_num, line in task_lines:
            parts = line.split(" | ")
            if len(parts) >= 4:
                refs_str = parts[2].strip()
                if refs_str and " " not in refs_str:
                    for rid in refs_str.split(","):
                        if rid and ID_RE.match(rid):
                            task_refs.add(rid)

        # M2: AC -> tasks (only for direct coverage; documented must NOT appear)
        for sid in spec_ac:
            ck = ck_of.get(sid, "")
            if (not ck or ck == "direct") and sid not in task_refs:
                add("M2", "HIGH", "tasks.md", f"{sid} is not referenced by any task")

        # M3: EDGE/INV -> tasks (only for direct coverage)
        for sid in spec_edge + spec_inv:
            ck = ck_of.get(sid, "")
            if (not ck or ck == "direct") and sid not in task_refs:
                add("M3", "HIGH", "tasks.md", f"{sid} is not referenced by any task")

        # M4: [USn] tasks reference >=1 spec ID
        for line_num, line in task_lines:
            if re.search(r"\[US\d+\]", line):
                parts = line.split(" | ")
                has_ref = False
                if len(parts) >= 4:
                    refs_str = parts[2].strip()
                    if refs_str and " " not in refs_str:
                        has_ref = any(ID_RE.match(r) for r in refs_str.split(",") if r)
                tid = re.search(r"T\d{3}", line)
                if not has_ref:
                    add(
                        "M4",
                        "MEDIUM",
                        f"tasks.md:{line_num}",
                        f"Story task {tid.group(0) if tid else '???'} references no spec ID",
                    )

        # M5 tasks side
        for sid in task_refs:
            if sid not in spec_ids:
                add("M5", "HIGH", "tasks.md", f"{sid} cited in tasks.md but not defined in spec.md")

        # M7: task numbering & format
        tnums = []
        for line_num, line in task_lines:
            m = re.search(r"T(\d{3})", line)
            if m:
                tnums.append(m.group(1))
        from collections import Counter

        dupes = [t for t, c in Counter(tnums).items() if c > 1]
        for d in dupes:
            add("M7", "MEDIUM", "tasks.md", f"Duplicate task ID T{d}")

        uniq_sorted = sorted(set(int(t) for t in tnums))
        if uniq_sorted:
            for n in range(uniq_sorted[0], uniq_sorted[-1] + 1):
                if n not in uniq_sorted:
                    add("M7", "MEDIUM", "tasks.md", f"Gap in task numbering: T{n:03d}")

        # M8: task paths in plan manifest
        if have_plan:
            manifest_paths = set()
            for line in _extract_pathmanifest(plan):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("<!--"):
                    parts = line.split()
                    if parts:
                        manifest_paths.add(parts[0].lstrip("./"))

            task_paths = set()
            for line_num, line in task_lines:
                parts = line.split(" | ")
                if len(parts) >= 2:
                    p = parts[1].strip().lstrip("./")
                    if p:
                        task_paths.add(p)

            for p in task_paths:
                if p not in manifest_paths:
                    add("M8", "HIGH", "tasks.md", f"Path '{p}' used in tasks.md but not in plan.md manifest")

        # M12: [P] tasks sharing paths
        p_paths = {}
        for line_num, line in task_lines:
            if re.search(r"T\d{3} \[P\]", line):
                tid = re.search(r"T\d{3}", line).group(0)
                parts = line.split(" | ")
                if len(parts) >= 2:
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
        for us in us_labels:
            uj = f"UJ-{int(us):03d}"
            if uj not in spec_uj:
                add("M14", "HIGH", "tasks.md", f"Label [US{us}] has no matching {uj} in spec.md")

    # M11: timestamp drift
    def mtime(p):
        return p.stat().st_mtime if p.exists() else 0

    mt_spec = mtime(spec)
    if have_plan:
        mt_plan = mtime(plan)
        if mt_spec > mt_plan:
            add("M11", "MEDIUM", "spec.md/plan.md", "spec.md modified after plan.md")
        if have_tasks:
            mt_tasks = mtime(tasks)
            if mt_plan > mt_tasks:
                add("M11", "MEDIUM", "plan.md/tasks.md", "plan.md modified after tasks.md")

    # M13: placeholder residue
    for f in [spec, plan, tasks]:
        if not f.exists():
            continue
        base = f.name
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"TODO|TKTK|\?\?\?|<placeholder>|\[path/to/", line):
                msg = line.strip()[:80]
                sev = "LOW"
                if "[path/to/" in line or "<placeholder>" in line:
                    sev = "MEDIUM"
                add("M13", sev, f"{base}:{i}", f"Placeholder residue: {msg}")

    # Summary
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
        import json

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


# ── dispatch ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="traceability.py")
    parser.add_argument("-C", "--root", default=None, help="Path to the project root directory")
    subparsers = parser.add_subparsers(dest="cmd")

    subparsers.add_parser("init", help="init <feature>")
    subparsers.add_parser("lint", help="lint <feature>")
    subparsers.add_parser("extract-spec-ids", help="extract-spec-ids <feature>")
    subparsers.add_parser("extract-trace", help="extract-trace <feature>")
    subparsers.add_parser("render", help="render <feature>")
    subparsers.add_parser("get", help="get <feature> <mechanisms|spec-ids|trace>")
    subparsers.add_parser("put-mechanisms", help="put-mechanisms <feature>")
    subparsers.add_parser("put-spec-ids", help="put-spec-ids <feature>")
    subparsers.add_parser("put-trace", help="put-trace <feature>")
    subparsers.add_parser("check-plan", help="check-plan <feature>")

    val_parser = subparsers.add_parser("validate", help="validate [--json] [--stage] <feature>")
    val_parser.add_argument("--json", action="store_true")
    val_parser.add_argument("--stage", choices=["spec", "plan", "tasks"])
    val_parser.add_argument("feature")

    args, remaining = parser.parse_known_args()
    cmd = args.cmd

    global _ROOT
    if args.root:
        _ROOT = Path(args.root).resolve()
    elif os.environ.get("ORDERSPEC_ROOT"):
        _ROOT = Path(os.environ["ORDERSPEC_ROOT"]).resolve()
    else:
        _ROOT = script_dir().parent.parent

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
        if len(remaining) < 2:
            die("usage: traceability.py get <feature> <mechanisms|spec-ids|trace>", 64)
        cmd_get(remaining[0], remaining[1])
    elif cmd == "put-mechanisms":
        cmd_put_mechanisms(remaining[0] if remaining else "")
    elif cmd == "put-spec-ids":
        cmd_put_spec_ids(remaining[0] if remaining else "")
    elif cmd == "put-trace":
        cmd_put_trace(remaining[0] if remaining else "")
    elif cmd == "check-plan":
        cmd_check_plan(remaining[0] if remaining else "")
    elif cmd == "validate":
        cmd_validate(args)
    else:
        parser.print_help()
        sys.exit(64)


if __name__ == "__main__":
    main()