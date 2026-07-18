#!/usr/bin/env python3
"""trace_commands.py — CLI command implementations for traceability."""

import json
import os
import re
import shutil
import sys
from pathlib import Path

from trace_constants import (
    FEATURE_STATE_DIRNAME, MECH_COLNAMES, MECH_MARKER,
    SPECIDS_COLNAMES, SPECIDS_MARKER,
    TRACE_COLNAMES, TRACE_MARKER,
    TAB, SPEC_PREFIX_RE, TASK_LINE_RE, _SPEC_ID_RE,
    SECTION_MAP,
)
from trace_tsv import _read_table, write_tsv_atomic, _lint_coverage
from trace_lint import lint_file
from trace_parse import (
    _extract_defined_ids_from_spec_text, _extract_id_texts,
    _extract_all_id_refs, _parse_pathmanifest, _sort_spec_id,
)

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


def set_root(root):
    global _ROOT
    _ROOT = root


def set_feature_dir_override(fd):
    global _FEATURE_DIR_OVERRIDE
    _FEATURE_DIR_OVERRIDE = fd


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
    return _read_active_feature_dir_from_active_feature_state()


def resolve_feature_dir(feature=None):
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


def cmd_put_mechanisms(feature, json_input=False):
    if json_input:
        data = json.loads(sys.stdin.read())
        rows = []
        for item in data:
            rows.append([
                item["spec_id"],
                item["coverage_kind"],
                item["mechanism"],
                item["primary_files"],
                item["test_type"],
            ])
        _put_via_lint(feature, "mechanisms", "mechanisms.tsv", MECH_MARKER, MECH_COLNAMES, rows=rows)
    else:
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
            f"WARNING: {sid} disappeared from spec.md \u2014 verify it was tombstoned "
            f"in \u00a72 Out-of-Scope, not silently renumbered",
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

            if len(parts) != 4:
                print(
                    f"extract-trace: task {tid} must contain exactly four pipe-delimited fields",
                    file=sys.stderr,
                )
                bug = True
                continue

            path = parts[1].strip().lstrip("./")
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


def cmd_suggest_tasks(feature, json_out=False):
    """Suggest task line skeletons by grouping direct mechanisms by primary_files.

    For each primary_files path that has direct mechanisms:
    - If ≤3 mechanisms: one suggestion with all refs
    - If >3 mechanisms (god-file): multiple suggestions, each ≤3 refs (sequential split)

    Also suggests infra tasks for barrel/index files in pathmanifest that have no
    direct mechanisms.

    Output: JSON or plain text with path | refs | gloss_hint per suggestion.
    """
    from collections import defaultdict

    sdir = state_dir(feature)
    mtsv = sdir / "mechanisms.tsv"

    if not mtsv.exists():
        die(f"suggest-tasks: mechanisms.tsv not found: {mtsv} (run put-mechanisms first)")

    plan = plan_path(feature)
    if not plan.exists():
        die(f"suggest-tasks: plan.md not found: {plan}")

    manifest_paths, manifest_errors = _parse_pathmanifest(plan)
    if manifest_errors:
        die(f"suggest-tasks: pathmanifest errors: {manifest_errors}")

    mech_rows = _read_table(mtsv, "mechanisms")

    # Group direct mechanisms by primary_files
    groups = defaultdict(list)
    for row in mech_rows:
        ck = row["coverage_kind"]
        if ck != "direct":
            continue
        pf = row["primary_files"].lstrip("./")
        if pf not in manifest_paths:
            continue
        groups[pf].append({
            "spec_id": row["spec_id"],
            "mechanism": row["mechanism"],
            "test_type": row["test_type"],
        })

    # Build suggestions
    suggestions = []
    for path in sorted(groups.keys()):
        mechs = sorted(groups[path], key=lambda x: _sort_spec_id(x["spec_id"]))
        needs_split = len(mechs) > 3

        # Split into chunks of 3
        for i in range(0, len(mechs), 3):
            chunk = mechs[i:i+3]
            refs = [m["spec_id"] for m in chunk]
            mech_summaries = [m["mechanism"] for m in chunk]
            gloss_hint = "; ".join(mech_summaries)
            if len(gloss_hint) > 80:
                gloss_hint = gloss_hint[:77] + "..."

            suggestions.append({
                "path": path,
                "refs": refs,
                "gloss_hint": gloss_hint,
                "needs_split": needs_split,
            })

    # Suggest infra tasks for barrel/index files without direct mechanisms
    for path in sorted(manifest_paths.keys()):
        if path in groups:
            continue
        tag = manifest_paths[path]
        if tag not in ("[MOD]", "[NEW]"):
            continue
        lower = path.lower()
        if "index" in lower or "barrel" in lower:
            suggestions.append({
                "path": path,
                "refs": [],
                "gloss_hint": "register in barrel/index (infra, no refs)",
                "needs_split": False,
            })

    if json_out:
        print(json.dumps({"suggestions": suggestions}, indent=2))
    else:
        print("# Suggested task skeletons (path | refs | gloss_hint):")
        for s in suggestions:
            refs_str = ",".join(s["refs"]) if s["refs"] else ""
            split_marker = " [SPLIT]" if s["needs_split"] else ""
            print(f"{s['path']} | {refs_str} | {s['gloss_hint']}{split_marker}")



def cmd_check_plan(feature):
    fdir = resolve_feature_dir(feature)
    plan = fdir / "plan.md"

    if not plan.exists():
        die(f"check-plan: plan.md not found: {plan}")

    rc = 0
    manifest_paths, manifest_errors = _parse_pathmanifest(plan)

    for err in manifest_errors:
        print(f"check-plan: ERROR \u2014 {err}", file=sys.stderr)
        rc = 1

    for path, tag in manifest_paths.items():
        full_path = resolved_root() / path

        if tag == "[MOD]" and not full_path.exists():
            print(f"check-plan: ERROR \u2014 [MOD] path does not exist: {path}", file=sys.stderr)
            rc = 1

        if tag == "[NEW]" and full_path.exists():
            print(f"check-plan: ERROR \u2014 [NEW] path already exists: {path}", file=sys.stderr)
            rc = 1

        if tag == "[DEL]" and not full_path.exists():
            print(f"check-plan: ERROR \u2014 [DEL] path does not exist: {path}", file=sys.stderr)
            rc = 1

    if rc == 0:
        print(f"check-plan: OK ({fdir.name})")
    else:
        print(f"check-plan: FAIL ({fdir.name}) \u2014 see errors above", file=sys.stderr)

    sys.exit(rc)


def cmd_check_mechanisms(feature):
    from trace_mechanisms import check_mechanisms_findings
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


# ── mark-consumed ────────────────────────────────────────────────────────────

def cmd_mark_consumed(args):
    report_path = Path(args.report)
    if not report_path.exists():
        die(f"mark-consumed: report file not found: {report_path}")

    marker = f"""<!-- orderspec-report-state: CONSUMED_STALE -->
# CONSUMED_STALE \u2014 {report_path.name}

This is not a PASS verdict.

The previous gate report was consumed by `{args.consumer}` and is now stale.
Run `{args.recheck}` for a fresh verdict.
"""
    report_path.write_text(marker, encoding="utf-8")
    print(f"mark-consumed: wrote CONSUMED_STALE marker to {report_path}")


# ── diff-summary ─────────────────────────────────────────────────────────────

def _git_show_spec(repo_root, git_ref, spec_rel_path):
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
    print(f"**Comparison**: `{summary['old_ref']}` \u2192 `{summary['new_ref']}`")
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

    old_text = _git_show_spec(resolved_root(), old_ref, spec_rel)

    if new_ref in ("HEAD", "WORKING", "INDEX"):
        new_text = spec.read_text(encoding="utf-8")
    else:
        new_text = _git_show_spec(resolved_root(), new_ref, spec_rel)

    old_ids = _extract_id_texts(old_text)
    new_ids = _extract_id_texts(new_text)

    old_set = set(old_ids.keys())
    new_set = set(new_ids.keys())

    added = sorted(new_set - old_set, key=_sort_spec_id)
    removed = sorted(old_set - new_set, key=_sort_spec_id)
    common = sorted(old_set & new_set, key=_sort_spec_id)

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
                details.append("weakened: MUST \u2192 SHOULD")
            elif old_should and new_must and not new_should:
                details.append("strengthened: SHOULD \u2192 MUST")

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
