#!/usr/bin/env python3
"""trace_mechanisms.py — mechanism cross-checks for traceability."""

from pathlib import Path

from trace_constants import REQUIRED_MECHANISM_PREFIXES
from trace_lint import lint_file
from trace_parse import _parse_pathmanifest, _sort_spec_id
from trace_tsv import _read_table


def _resolve_terminal_mechanism(mech_by_id, spec_id):
    """Return terminal delegated mechanism as ``(spec_id, row)``.

    Delegated rows inherit evidence topology from their terminal direct or
    documented row. Invalid delegation is reported separately by the
    existing M17 checks, so unresolved chains are ignored here.
    """
    seen = set()
    current = spec_id

    while current not in seen:
        seen.add(current)
        row = mech_by_id.get(current)
        if not row:
            return None, None

        coverage_kind = row.get("coverage_kind", "")
        if coverage_kind in {"direct", "documented"}:
            return current, row
        if not coverage_kind.startswith("delegated:"):
            return None, None
        current = coverage_kind[len("delegated:"):]

    return None, None


def _check_test_topology_findings(mech_rows, manifest_paths):
    """Ensure declared unit/integration evidence has a planned test path."""
    mech_by_id = {row["spec_id"]: row for row in mech_rows}
    active_paths = {
        path
        for path, tag in manifest_paths.items()
        if tag != "[DEL]"
    }

    available_paths = {
        "unit": any(path.startswith("tests/unit/") for path in active_paths),
        "integration": any(path.startswith("tests/integration/") for path in active_paths),
    }
    findings = []

    for row in sorted(mech_rows, key=lambda item: _sort_spec_id(item["spec_id"])):
        spec_id = row["spec_id"]
        coverage_kind = row.get("coverage_kind", "")

        if coverage_kind == "documented":
            continue
        if coverage_kind != "direct" and not coverage_kind.startswith("delegated:"):
            continue

        terminal_id, terminal_row = _resolve_terminal_mechanism(mech_by_id, spec_id)
        if not terminal_row or terminal_row.get("coverage_kind") == "documented":
            continue

        test_type = terminal_row.get("test_type", "")
        if test_type not in available_paths or available_paths[test_type]:
            continue

        if terminal_id == spec_id:
            detail = f"{spec_id} declares test_type={test_type}"
        else:
            detail = (
                f"{spec_id} delegates to {terminal_id}, which declares "
                f"test_type={test_type}"
            )
        findings.append(
            (
                "M37",
                "HIGH",
                "plan.md:pathmanifest",
                f"{detail}, but pathmanifest has no tests/{test_type}/ test path",
            )
        )

    return findings


def check_mechanisms_findings(feature=None):
    from trace_commands import resolve_feature_dir, state_dir_for_feature_dir, resolved_root

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

    if not manifest_errors:
        findings.extend(_check_test_topology_findings(mech_rows, manifest_paths))

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
