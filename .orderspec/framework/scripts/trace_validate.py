#!/usr/bin/env python3
"""trace_validate.py — validation checks for traceability."""

import json
import re
import sys
from pathlib import Path

from trace_constants import (
    ABSOLUTE_QUANTIFIERS, AC_COVERS_RE,
    IF_REQUIRED_FIELDS, SPEC_PREFIX_RE, SPEC_PREFIXES, ID_RE, TASK_LINE_RE, COVERS_RE,
    _SPEC_ID_RE,
)
from trace_mechanisms import check_mechanisms_findings
from trace_parse import (
    _extract_ac_inline_covers, _extract_all_id_refs, _extract_defined_ids_from_spec_text,
    _extract_grid_rows, _extract_id_texts, _extract_information_model,
    _extract_if_records, _extract_inv_texts, _extract_section,
    _extract_status_codes, _parse_pathmanifest, _sort_spec_id,
)
from trace_lint import lint_file
from trace_tsv import _read_table

DISPOSITION_MAP = {
    "M1": "Route", "M1a": "Route", "M6": "Route", "M11": "Informational",
    "M13": "Route", "M18": "Route", "M19": "Route", "M20": "Route",
    "M21": "Route", "M22": "Informational", "M23": "Route", "M24": "Route",
    "M25": "Route", "M28": "Route", "M29": "Route", "M30": "Route",
    "M31": "Route", "M32": "Route", "M33": "Route", "M34": "Route",
    "M35": "Route", "M36": "Route", "M37": "Route"
}

def _load_specids(feature=None):
    from trace_commands import state_dir
    sdir = state_dir(feature)
    path = sdir / "spec-ids.tsv"
    if not path.exists():
        return {}
    rows = _read_table(path, "specids")
    return {row["spec_id"]: row for row in rows}


def _defined_ids(feature=None):
    from trace_commands import spec_path
    specids = _load_specids(feature)
    if specids:
        return set(specids.keys())
    sp = spec_path(feature)
    if not sp.exists():
        return set()
    return _extract_defined_ids_from_spec_text(sp.read_text(encoding="utf-8"))


def _make_add(findings):
    def add(check, severity, location, message):
        findings.append({
            "check": check,
            "severity": severity,
            "location": location,
            "message": message,
            "disposition": DISPOSITION_MAP.get(check, "Route")
        })
    return add


def _check_m6(spec_text, add):
    for i, line in enumerate(spec_text.splitlines(), start=1):
        if re.search(r"\bQ-\d+\b|\[NEEDS CLARIFICATION", line):
            add("M6", "HIGH", f"spec.md:{i}", f"Unresolved clarification: {line.strip()}")


def _check_m28(spec_text, add):
    from frontmatter import validate_spec_frontmatter
    fm_errors = validate_spec_frontmatter(spec_text)
    for field, message in fm_errors:
        add("M28", "HIGH", "spec.md:frontmatter", message)


def _check_m1(spec_text, defined_ids, add):
    req_ids = {sid for sid in defined_ids if sid.startswith("REQ-")}
    covers_ids = set()
    for line in spec_text.splitlines():
        if COVERS_RE.match(line):
            covers_ids |= _extract_all_id_refs(line)

    for sid in sorted(req_ids, key=_sort_spec_id):
        if sid not in covers_ids:
            add("M1", "HIGH", "spec.md", f"{sid} is not listed in any UJ 'Covers'")


def _check_m1a(spec_text, defined_ids, add):
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


def _check_m18(if_records, add):
    for if_id, rec in if_records.items():
        fields = rec["fields"]
        for field_name, sev in IF_REQUIRED_FIELDS:
            if field_name not in fields or not fields[field_name].strip():
                add("M18", sev, "spec.md:\u00a79", f"{if_id} missing required field '{field_name}'")


def _check_m19(if_records, if_to_acs, section_12, add):
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
                                "spec.md:\u00a712",
                                f"{ac_id} references status {st} for {if_id} but it is not in IF Success/Failure",
                            )
                    break


def _check_m29(if_records, if_to_acs, section_12, add):
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

        covering_acs = if_to_acs.get(if_id, set())

        ac_statuses_for_if = set()
        for ac_id in covering_acs:
            for line in section_12.splitlines():
                if line.strip().startswith(f"- **{ac_id}**"):
                    ac_statuses_for_if |= _extract_status_codes(line)
                    break

        for st in sorted(if_success_statuses):
            if st not in ac_statuses_for_if:
                add(
                    "M29",
                    "HIGH",
                    "spec.md:\u00a79",
                    f"{if_id} Success status {st} is not covered by any AC",
                )

        for st in sorted(if_failure_statuses):
            if st not in ac_statuses_for_if:
                add(
                    "M29",
                    "MEDIUM",
                    "spec.md:\u00a79",
                    f"{if_id} Failure status {st} is not covered by any AC (consider adding AC for this failure path)",
                )


def _check_m20(if_records, if_to_acs, add):
    for if_id in if_records:
        if if_id not in if_to_acs or not if_to_acs[if_id]:
            add("M20", "HIGH", "spec.md:\u00a79", f"{if_id} is not covered by any AC via [Covers: ...]")


def _check_m21(if_records, defined_ids, add):
    for if_id, rec in if_records.items():
        fields = rec["fields"]
        link_field = fields.get("Covers") or fields.get("Related") or ""
        if not link_field:
            continue
        for m in ID_RE.finditer(link_field):
            ref_id = f"{m.group(1)}-{m.group(2)}"
            if ref_id not in defined_ids:
                add("M21", "HIGH", "spec.md:\u00a79", f"{if_id} Covers references unknown {ref_id}")


def _check_m22(section_12, section_8, add):
    info_model = _extract_information_model(section_8) if section_8 else {}
    all_known_fields = set()
    for fld_set in info_model.values():
        all_known_fields |= fld_set

    envelope_fields = {
        "results", "page", "limit", "totalPages", "totalResults",
        "total", "data", "items", "count", "nextCursor", "prevCursor", "cursor",
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
                        "spec.md:\u00a712",
                        f"{ac_id} checks field '{field_name}' not found in \u00a78 Information Model",
                    )


def _check_m23(grid_rows, anchor_ids, add):
    for row in grid_rows:
        left_id = row.get("left_id")
        right_id = row.get("right_id")
        if left_id and left_id not in anchor_ids:
            add("M23", "MEDIUM", "spec.md:\u00a710", f"Grid left ID {left_id} not defined in spec")
        if right_id and right_id not in anchor_ids:
            add("M23", "MEDIUM", "spec.md:\u00a710", f"Grid right ID {right_id} not defined in spec")


def _check_m24(inv_texts, grid_rows, add):
    grid_left_ids = {row.get("left_id") for row in grid_rows}
    for inv_id, text in inv_texts.items():
        text_lower = text.lower()
        if any(q in text_lower for q in ABSOLUTE_QUANTIFIERS):
            if inv_id not in grid_left_ids:
                add(
                    "M24",
                    "MEDIUM",
                    "spec.md:\u00a710",
                    f"{inv_id} uses absolute quantifier but has no row in Contradiction Grid",
                )


def _check_m25(grid_rows, add):
    seen = set()
    dupes = 0
    for row in grid_rows:
        key = (row.get("left_id"), row.get("right_id"))
        if key in seen:
            dupes += 1
        seen.add(key)
    if dupes > 0:
        add("M25", "MEDIUM", "spec.md:\u00a710", f"Duplicate rows found in Contradiction Grid ({dupes})")


def _check_m13(files, add):
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"TODO|TKTK|\?\?\?|<placeholder>|\[path/to/|NEEDS CLARIFICATION|Optional forced upstream-gate warning|verdict: \.\.\.|semicolon-separated|\[Failure outcomes\]|\[Success outcomes\]|None \(.*\)", line):
                sev = "MEDIUM" if "<placeholder>" in line or "[path/to/" in line else "LOW"
                add("M13", sev, f"{f.name}:{i}", f"Placeholder residue: {line.strip()[:100]}")


def _check_plan_refs(plan, defined_ids, add):
    plan_text = plan.read_text(encoding="utf-8")
    plan_refs = _extract_all_id_refs(plan_text)
    for sid in sorted(plan_refs - defined_ids, key=_sort_spec_id):
        add("M5", "HIGH", "plan.md", f"{sid} cited in plan.md but not defined in spec-ids.tsv/spec.md anchors")


def _check_plan_manifest(plan, add):
    from trace_commands import resolved_root
    manifest_paths, manifest_errors = _parse_pathmanifest(plan)
    for err in manifest_errors:
        add("M9", "HIGH", "plan.md", err)
    for path, tag in manifest_paths.items():
        full_path = resolved_root() / path
        if tag == "[MOD]" and not full_path.exists():
            add("M10", "HIGH", "plan.md", f"[MOD] path '{path}' does not exist in repo")
        elif tag == "[NEW]" and full_path.exists():
            add("M10", "HIGH", "plan.md", f"[NEW] path '{path}' already exists in repo")
        elif tag == "[DEL]" and not full_path.exists():
            add("M10", "HIGH", "plan.md", f"[DEL] path '{path}' does not exist in repo")


def _check_tasks_coverage(ac_ids, defined_ids, task_refs, ck_of, add):
    edge_ids = {sid for sid in defined_ids if sid.startswith("EDGE-")}
    inv_ids = {sid for sid in defined_ids if sid.startswith("INV-")}

    for sid in sorted(ac_ids, key=_sort_spec_id):
        ck = ck_of.get(sid, "")
        if (not ck or ck == "direct") and sid not in task_refs:
            add("M2", "HIGH", "tasks.md", f"{sid} is not referenced by any task")

    for sid in sorted(edge_ids | inv_ids, key=_sort_spec_id):
        ck = ck_of.get(sid, "")
        if (not ck or ck == "direct") and sid not in task_refs:
            add("M3", "HIGH", "tasks.md", f"{sid} is not referenced by any task")


def _check_m4(task_lines, direct_primary_files, add):
    for line_num, line in task_lines:
        if not re.search(r"\[US\d+\]", line):
            continue
        parts = line.split(" | ")
        task_path = parts[1].strip().lstrip("./") if len(parts) >= 2 else ""
        if task_path not in direct_primary_files:
            continue
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


def _check_m5_tasks(task_refs, defined_ids, add):
    for sid in sorted(task_refs - defined_ids, key=_sort_spec_id):
        add("M5", "HIGH", "tasks.md", f"{sid} cited in tasks.md but not defined in spec-ids.tsv/spec.md anchors")


def _check_m8(task_paths, plan, add):
    manifest_paths, _ = _parse_pathmanifest(plan)
    for p in sorted(task_paths):
        if p not in manifest_paths:
            add("M8", "HIGH", "tasks.md", f"Path '{p}' used in tasks.md but not in plan.md manifest")


def _check_m12(task_lines, add):
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


def _check_m14(task_lines, uj_ids, add):
    us_labels = set()
    for line_num, line in task_lines:
        for m in re.finditer(r"\[US(\d+)\]", line):
            us_labels.add(m.group(1))
    for us in sorted(us_labels, key=lambda x: int(x)):
        uj = f"UJ-{int(us):03d}"
        if uj not in uj_ids:
            add("M14", "HIGH", "tasks.md", f"Label [US{us}] has no matching {uj} in spec.md")


def _check_m7(task_lines, add):
    """M7: duplicate task IDs are rejected. Gaps in numbering are ALLOWED
    (e.g. T005, T010, T015) to reduce churn when inserting tasks mid-pipeline."""
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


def _check_m30(spec_text, defined_ids, ac_inline_covers, add):
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
            add("M30", "MEDIUM", "spec.md:\u00a711", f"{sid} has no AC coverage and is not marked deferred")


def _check_m31(spec_text, add):
    uj_p1_ids = []
    for line in spec_text.splitlines():
        m_uj = re.match(r"^\s*- \*\*(UJ-\d{3})\*\*", line)
        if not m_uj:
            continue
        if re.search(r"Priority:\s*P1", line, re.IGNORECASE):
            uj_p1_ids.append(m_uj.group(1))
    if len(uj_p1_ids) > 2:
        add("M31", "MEDIUM", "spec.md:\u00a712", f"More than 2 P1 UJs found ({len(uj_p1_ids)}): {', '.join(uj_p1_ids)}")


def _check_m32(spec_text, add):
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


def _check_contract_risks(spec_text, if_records, section_9, add):
    """Catch high-value contract gaps that lexical coverage cannot prove.

    These checks deliberately flag only explicit wording patterns. They do not
    decide the product behaviour; they force the owner command to resolve a
    missing decision before plan/tasks can turn it into code.
    """
    id_texts = _extract_id_texts(spec_text)

    # An exact-one audit guarantee spans at least two writes. Without an
    # atomic, compensating, or explicitly partial-failure policy, the contract
    # has no defined behaviour when the second write fails.
    has_exact_one_audit = bool(
        re.search(r"exactly\s+one\s+(?:corresponding\s+)?audit(?:\s+log)?", spec_text, re.IGNORECASE)
        or re.search(r"one\s+audit\s+log\s+entry", spec_text, re.IGNORECASE)
    )
    has_failure_policy = bool(
        re.search(
            r"\b(?:atomic(?:ity)?|transaction(?:al)?|all[- ]or[- ]nothing|"
            r"compensat(?:e|ion|ing)|rollback|partial[- ]failure|best[- ]effort)\b",
            spec_text,
            re.IGNORECASE,
        )
    )
    if has_exact_one_audit and not has_failure_policy:
        add(
            "M33",
            "HIGH",
            "spec.md:\u00a710 / \u00a714",
            "Exact-one audit guarantee has no atomicity, compensation, or partial-failure semantics",
        )

    # Pagination is not a complete contract when it is only named as an input
    # and the response shape remains an unqualified array.
    for if_id, record in if_records.items():
        input_text = record["fields"].get("Input", "")
        if not re.search(r"\bpagination\b", input_text, re.IGNORECASE):
            continue
        has_envelope = bool(
            re.search(r"pagination\s+envelope", section_9, re.IGNORECASE)
            or re.search(r"\bCONV-\d{3}\b", section_9)
        )
        if not has_envelope:
            add(
                "M34",
                "HIGH",
                f"spec.md:\u00a79 ({if_id})",
                "Pagination is named in interface input without a response envelope or CONV definition",
            )

    # Detect a direct contradiction that is easy for a weak model to miss:
    # an edge says a newly-created entity has no audit history while a core
    # requirement says creation always writes an audit entry.
    create_audit_ids = [
        sid for sid, text in id_texts.items()
        if sid.startswith(("REQ-", "INV-"))
        and "audit" in text.lower()
        and re.search(r"\b(?:every|each|all)\b", text, re.IGNORECASE)
        and re.search(r"audit.*creat|creat.*audit", text, re.IGNORECASE)
    ]
    for sid, text in id_texts.items():
        if not sid.startswith("EDGE-"):
            continue
        lowered = text.lower()
        says_no_history = bool(
            re.search(r"no\s+audit(?:\s+history)?", lowered)
            or re.search(r"empty\s+audit(?:\s+history)?", lowered)
            or re.search(r"audit(?:\s+history)?[^\n]*empty\s+array", lowered)
        )
        if says_no_history and create_audit_ids and re.search(r"newly|new|created", lowered):
            add(
                "M35",
                "HIGH",
                f"spec.md:\u00a711 ({sid})",
                f"{sid} conflicts with creation-audit guarantee(s): {', '.join(create_audit_ids)}",
            )

    # A requirement for changed-field deltas and a decision for full snapshots
    # need an explicit reconciliation. Otherwise tests and implementation can
    # both appear correct while recording different meanings of "before/after".
    has_changed_fields = any(
        "changed fields" in text.lower()
        for sid, text in id_texts.items()
        if sid.startswith(("REQ-", "IF-", "AC-"))
    )
    has_full_snapshots = any(
        "full" in text.lower() and "snapshot" in text.lower()
        for sid, text in id_texts.items()
        if sid.startswith("DEC-")
    )
    if has_changed_fields and has_full_snapshots:
        add(
            "M36",
            "HIGH",
            "spec.md:\u00a74 / \u00a714",
            "Contract mixes changed-field audit semantics with a full-snapshot decision without reconciliation",
        )


def _check_m11(spec, plan, tasks, have_plan, have_tasks, add):
    if have_plan and spec.stat().st_mtime > plan.stat().st_mtime:
        add("M11", "MEDIUM", "spec.md/plan.md", "spec.md modified after plan.md")
    if have_plan and have_tasks and plan.stat().st_mtime > tasks.stat().st_mtime:
        add("M11", "MEDIUM", "plan.md/tasks.md", "plan.md modified after tasks.md")


def _category_heading_blocks(spec_text):
    """Return normalized Markdown heading blocks for category detection.

    Feature specs can use numbered or unnumbered headings and may place a
    category at different heading levels. Category detection must follow the
    heading title, not a fixed section number.
    """
    lines = spec_text.splitlines()
    headings = []
    for index, line in enumerate(lines):
        match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue

        title = re.sub(r"\s+#+\s*$", "", match.group(2)).strip()
        title = re.sub(r"^\d+(?:\.\d+)*[.)]?\s+", "", title).strip()
        headings.append((index, len(match.group(1)), title.lower()))

    blocks = []
    for position, (start, level, title) in enumerate(headings):
        end = len(lines)
        for next_start, next_level, _ in headings[position + 1:]:
            if next_level <= level:
                end = next_start
                break
        body = "\n".join(lines[start + 1:end])
        blocks.append((level, title, body))
    return blocks


def _category_body_has_content(body):
    """Return whether a category block contains meaningful non-heading text."""
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            continue
        return True
    return False


def _compute_categories(spec_text):
    """Compute coverage categories from semantic headings, not section numbers.

    Older specs use headings such as ``## 3. Requirements`` while the current
    template uses ``## 4. Functional Requirements`` and nested
    ``### Success Criteria``. Both forms are valid and must produce the same
    taxonomy. ID-backed categories are accepted as a fallback when content was
    authored without a dedicated heading.
    """
    blocks = _category_heading_blocks(spec_text)
    headings = [(title, body) for _, title, body in blocks]

    def has_heading(predicate):
        return any(predicate(title) and _category_body_has_content(body) for title, body in headings)

    def has_id(prefix):
        return bool(re.search(rf"^\s*-\s*\*\*{prefix}-\d{{3}}\*\*:", spec_text, re.MULTILINE))

    category_matchers = {
        "Functional Requirements": lambda title: (
            title == "requirements"
            or (
                "functional requirements" in title
                and not title.startswith("non-functional requirements")
            )
        ),
        "Non-Functional Requirements": lambda title: (
            "non-functional requirements" in title
            or title.startswith("nfr")
        ),
        "Project Constraints Applied": lambda title: "project constraints" in title,
        "Architecture & Behaviour": lambda title: (
            "architecture" in title or "behaviour" in title or "behavior" in title
        ),
        "Information Model": lambda title: "information model" in title,
        "Interface Contracts": lambda title: "interface contracts" in title,
        "Invariants": lambda title: "invariant" in title,
        "Edge Cases": lambda title: "edge case" in title,
        "Acceptance Criteria & User Journeys": lambda title: (
            "acceptance criteria" in title or "user journey" in title
        ),
        "Open Questions": lambda title: "open question" in title,
        "Decisions": lambda title: "decision" in title,
        "Assumptions": lambda title: "assumption" in title,
        "Success Criteria": lambda title: "success criteria" in title,
        "Glossary": lambda title: title == "glossary",
        "Changelog": lambda title: title == "changelog",
    }

    id_fallbacks = {
        "Functional Requirements": "REQ",
        "Non-Functional Requirements": "NFR",
        "Interface Contracts": "IF",
        "Invariants": "INV",
        "Edge Cases": "EDGE",
        "Acceptance Criteria & User Journeys": "UJ|AC",
        "Open Questions": "Q",
        "Decisions": "DEC",
        "Assumptions": "ASM",
        "Success Criteria": "SC",
    }

    result = {}
    for name, predicate in category_matchers.items():
        present = has_heading(predicate)
        fallback = id_fallbacks.get(name)
        if not present and fallback:
            present = any(has_id(prefix) for prefix in fallback.split("|"))
        result[name] = "present" if present else "missing"

    return result


def _compute_journey_matrix(section_12_text, ac_inline_covers):
    matrix = []
    current_uj = None
    uj_covers = []
    uj_priority = ""
    uj_acs = []

    def flush_current():
        nonlocal current_uj, uj_covers, uj_priority, uj_acs
        if not current_uj:
            return
        traces = any(
            any(r.startswith("REQ-") for r in ac_inline_covers.get(ac, []))
            for ac in uj_acs
        )
        matrix.append({
            "uj_id": current_uj,
            "priority": uj_priority,
            "covers_reqs": uj_covers,
            "acs": uj_acs,
            "acs_trace_to_reqs": traces,
            "status": "ok",
        })
        current_uj = None
        uj_covers = []
        uj_priority = ""
        uj_acs = []

    for line in section_12_text.splitlines():
        heading = re.match(r"^\s*(#{1,6})\s+", line)
        if current_uj and heading and len(heading.group(1)) <= 2:
            # A separate top-level section usually contains UJs in §11 and
            # ACs in §12. Do not attach all later ACs to the last UJ when no
            # explicit nesting or mapping exists.
            flush_current()

        m_uj = re.match(r"^\s*- \*\*(UJ-\d{3})\*\*:?\s*(.*)", line)
        if m_uj:
            flush_current()
            current_uj = m_uj.group(1)
            uj_covers = []
            uj_priority = ""
            uj_acs = []

        if current_uj:
            m_prio = re.search(r"Priority\s*:\s*(P\d)", line, re.IGNORECASE)
            if not m_prio:
                m_prio = re.search(r"\|\s*Priority\s*\|\s*(P\d)", line, re.IGNORECASE)
            if m_prio:
                uj_priority = m_prio.group(1)
            m_cov = re.search(r"^\s*(?:\*\*)?Covers(?:\*\*)?\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
            if not m_cov:
                m_cov = re.search(r"^\s*\|\s*Covers\s*\|\s*(.*?)\s*\|\s*$", line, re.IGNORECASE)
            if m_cov:
                _all_refs = [f"{m[0]}-{m[1]}" for m in ID_RE.findall(m_cov.group(1))]
                uj_covers = [r for r in _all_refs if r.startswith("REQ-")]

            m_ac = re.match(r"^\s*- \*\*(AC-\d{3})\*\*", line)
            if m_ac:
                uj_acs.append(m_ac.group(1))

    flush_current()
    return matrix


def _compute_if_matrix(if_records, if_to_acs):
    matrix = []
    for if_id, rec in if_records.items():
        fields = rec["fields"]
        matrix.append({
            "if_id": if_id,
            "kind": fields.get("Kind", ""),
            "actor": fields.get("Actor", ""),
            "success": ", ".join(sorted(_extract_status_codes(fields.get("Success", "")))) or fields.get("Success", ""),
            "failure": ", ".join(sorted(_extract_status_codes(fields.get("Failure", "")))) or fields.get("Failure", ""),
            "success_full": fields.get("Success", ""),
            "failure_full": fields.get("Failure", ""),
            "covered_by_acs": sorted(list(if_to_acs.get(if_id, set()))),
            "status": "ok" if if_to_acs.get(if_id) else "uncovered"
        })
    return matrix


def cmd_validate(args):
    from trace_commands import resolve_feature_dir, die, state_dir

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
    add = _make_add(findings)

    spec_text = spec.read_text(encoding="utf-8")
    defined_ids = _defined_ids(feature)
    anchor_ids = _extract_defined_ids_from_spec_text(spec_text)

    if not defined_ids:
        defined_ids = anchor_ids

    _check_m6(spec_text, add)
    _check_m28(spec_text, add)
    _check_m1(spec_text, defined_ids, add)

    ac_ids = {sid for sid in defined_ids if sid.startswith("AC-")}
    _check_m1a(spec_text, defined_ids, add)

    section_8 = _extract_section(spec_text, "## 8.")
    section_9 = _extract_section(spec_text, "## 9.")
    section_10 = _extract_section(spec_text, "## 10.")
    section_11 = _extract_section(spec_text, "## 11.")
    section_12 = _extract_section(spec_text, "## 12.")
    acceptance_sections = "\n".join(section for section in (section_11, section_12) if section)

    if_records = _extract_if_records(section_9) if section_9 else {}
    _check_m18(if_records, add)

    ac_inline_covers = _extract_ac_inline_covers(acceptance_sections) if acceptance_sections else {}

    if_to_acs = {}
    for ac_id, covers_list in ac_inline_covers.items():
        for ref in covers_list:
            if_to_acs.setdefault(ref, set()).add(ac_id)

    _check_m19(if_records, if_to_acs, acceptance_sections, add)
    _check_m29(if_records, if_to_acs, acceptance_sections, add)
    _check_m20(if_records, if_to_acs, add)
    _check_m21(if_records, defined_ids, add)
    _check_m22(acceptance_sections, section_8, add)

    grid_rows = _extract_grid_rows(section_10) if section_10 else []
    _check_m23(grid_rows, anchor_ids, add)

    inv_texts = _extract_inv_texts(spec_text)
    _check_m24(inv_texts, grid_rows, add)
    _check_m25(grid_rows, add)

    files_for_placeholder_scan = [spec]
    if have_plan:
        files_for_placeholder_scan.append(plan)
    if have_tasks:
        files_for_placeholder_scan.append(tasks)
    _check_m13(files_for_placeholder_scan, add)

    if stage in {"plan", "tasks"}:
        _check_plan_refs(plan, defined_ids, add)
        for check, severity, location, message in check_mechanisms_findings(feature):
            add(check, severity, location, message)

    # M10 validates the repository baseline observed by /order.plan. During
    # tasking, especially after partial implementation, applied [NEW]/[DEL]
    # transitions are expected work-order state rather than plan drift.
    if stage == "plan":
        _check_plan_manifest(plan, add)

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

        ck_of = {}
        direct_primary_files = set()
        mtsv = state_dir(feature) / "mechanisms.tsv"
        if mtsv.exists() and not lint_file(mtsv, "mechanisms"):
            try:
                for row in _read_table(mtsv, "mechanisms"):
                    ck_of[row["spec_id"]] = row.get("coverage_kind", "")
                    if row.get("coverage_kind", "") == "direct":
                        primary_file = row.get("primary_files", "").strip().lstrip("./")
                        if primary_file:
                            direct_primary_files.add(primary_file)
            except ValueError:
                ck_of = {}
                direct_primary_files = set()

        uj_ids = {sid for sid in defined_ids if sid.startswith("UJ-")}

        _check_tasks_coverage(ac_ids, defined_ids, task_refs, ck_of, add)
        _check_m4(task_lines, direct_primary_files, add)
        _check_m5_tasks(task_refs, defined_ids, add)
        _check_m8(task_paths, plan, add)
        _check_m12(task_lines, add)
        _check_m14(task_lines, uj_ids, add)
        _check_m7(task_lines, add)

    _check_m30(spec_text, defined_ids, ac_inline_covers, add)
    _check_m31(spec_text, add)
    _check_m32(spec_text, add)
    _check_contract_risks(spec_text, if_records, section_9, add)
    _check_m11(spec, plan, tasks, have_plan, have_tasks, add)

    total = len(findings)
    nc = sum(1 for f in findings if f["severity"] == "CRITICAL")
    nh = sum(1 for f in findings if f["severity"] == "HIGH")
    nm = sum(1 for f in findings if f["severity"] == "MEDIUM")
    nl = sum(1 for f in findings if f["severity"] == "LOW")

    exit_code = 1 if (nc + nh) > 0 else 0
    pass_allowed = nc == 0
    block_required = nc > 0
    verdict_floor = "PASS" if nc == 0 and nh == 0 else ("BLOCK" if nc > 0 else "ROUTING_REQUIRED")

    # compute inventory
    inv = {}
    for p in SPEC_PREFIXES:
        inv[p] = 0
    for sid in defined_ids:
        p = sid.split("-")[0]
        if p in inv:
            inv[p] += 1
    inv["Total"] = sum(inv.values())

    # compute categories
    cats = _compute_categories(spec_text)

    # enrich categories with inventory counts
    _CAT_PREFIX_MAP = {
        "Functional Requirements": ("REQ", "REQs"),
        "Non-Functional Requirements": ("NFR", "NFRs"),
        "Interface Contracts": ("IF", "IFs"),
        "Invariants": ("INV", "INVs"),
        "Edge Cases": ("EDGE", "EDGEs"),
        "Decisions": ("DEC", "DECs"),
        "Assumptions": ("ASM", "ASMs"),
        "Success Criteria": ("SC", "SCs"),
        "Open Questions": ("Q", "Qs"),
    }
    for _cat, (_pfx, _unit) in _CAT_PREFIX_MAP.items():
        if cats.get(_cat) == "present":
            _cnt = inv.get(_pfx, 0)
            _lbl = _unit if _cnt != 1 else _unit.rstrip("s")
            cats[_cat] = f"present \u2014 {_cnt} {_lbl}"
    if cats.get("Acceptance Criteria & User Journeys") == "present":
        cats["Acceptance Criteria & User Journeys"] = f"present \u2014 {inv.get('UJ', 0)} UJ, {inv.get('AC', 0)} AC"

    # compute matrices
    uj_matrix = _compute_journey_matrix(acceptance_sections, ac_inline_covers) if acceptance_sections else []
    if_matrix = _compute_if_matrix(if_records, if_to_acs) if if_records else []

    # extract contradiction grid
    grid = _extract_grid_rows(section_10) if section_10 else []

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
            "inventory": inv,
            "categories": cats,
            "matrices": {
                "uj_coverage": uj_matrix,
                "if_coverage": if_matrix
            },
            "contradiction_grid": grid,
            "findings": findings,
        }
        print(json.dumps(output))
    else:
        print(f"=== validate: {fdir} (stage={stage}) ===")
        print(f"Scope: spec=true plan={have_plan} tasks={have_tasks}")
        if total == 0:
            print("RESULT: CLEAN \u2014 no mechanical findings.")
        else:
            print(f"Findings: {total} (CRITICAL={nc} HIGH={nh} MEDIUM={nm} LOW={nl})")
            for f in findings:
                print(f"[{f['severity']}] {f['check']} ({f['location']}): {f['message']}")

    sys.exit(exit_code)
