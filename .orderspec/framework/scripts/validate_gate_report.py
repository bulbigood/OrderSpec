#!/usr/bin/env python3
"""Validate spec/plan/tasks gate reports against mechanical validator output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


COMMAND_IDS = {
    "order.spec-check": re.compile(r"^S1-\d{3}$"),
    "order.plan-check": re.compile(r"^P1-\d{3}$"),
    "order.tasks-check": re.compile(r"^T[1-8]-\d{3}$"),
}
OPERATIONAL_IDS = {
    "order.spec-check": re.compile(r"^S0-\d{3}$"),
    "order.plan-check": re.compile(r"^P0-\d{3}$"),
    "order.tasks-check": re.compile(r"^T0-\d{3}$"),
}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
DISPOSITIONS = {"Route", "Informational"}


def emit(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def frontmatter_value(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*[\"']?([^\"'\n]+)[\"']?\s*$", text)
    return match.group(1).strip() if match else None


def table_cells(line: str) -> list[str]:
    value = line.strip()
    if not value.startswith("|") or not value.endswith("|"):
        return []
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in value[1:-1]:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def findings_rows(text: str) -> list[dict[str, str]]:
    match = re.search(r"(?ms)^### Findings\s*$\n(.*?)(?=^### |\Z)", text)
    if not match:
        return []
    rows = []
    for line in match.group(1).splitlines():
        cells = table_cells(line)
        if len(cells) != 6 or cells[0] in {"ID", "----", "(none)"}:
            continue
        rows.append(dict(zip(("id", "source", "severity", "disposition", "location", "summary"), cells)))
    return rows


def validate(report: Path, mechanical: Path) -> tuple[dict, int]:
    errors: list[str] = []
    try:
        text = report.read_text(encoding="utf-8")
        validation = json.loads(mechanical.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "validation_errors": [str(exc)]}, 2

    command = frontmatter_value(text, "command")
    verdict = frontmatter_value(text, "verdict")
    if command not in COMMAND_IDS:
        errors.append("frontmatter command must be order.spec-check, order.plan-check, or order.tasks-check")
    if re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", text):
        errors.append("report contains unresolved template placeholders")

    rows = findings_rows(text)
    if not rows and "| (none) |" not in text:
        errors.append("Findings table is missing or malformed")

    mechanical_rows = [row for row in rows if row["source"].lower() == "mechanical"]
    semantic_rows = [row for row in rows if row["source"].lower() == "semantic"]
    operational_rows = [row for row in rows if row["source"].lower() == "operational"]
    unknown_sources = [
        row["source"]
        for row in rows
        if row["source"].lower() not in {"mechanical", "semantic", "operational"}
    ]
    if unknown_sources:
        errors.append(f"unknown finding sources: {sorted(set(unknown_sources))}")

    expected = Counter(
        (item.get("check", ""), item.get("severity", ""), item.get("disposition", ""), item.get("location", ""))
        for item in validation.get("findings", [])
    )
    actual = Counter(
        (item["id"], item["severity"], item["disposition"], item["location"])
        for item in mechanical_rows
    )
    for key, count in expected.items():
        if actual[key] < count:
            errors.append(f"mechanical finding missing or altered: {key} expected {count}, found {actual[key]}")
    for key, count in actual.items():
        if count > expected[key]:
            errors.append(f"unexpected mechanical finding row: {key}")

    semantic_ids = [row["id"] for row in semantic_rows]
    if len(semantic_ids) != len(set(semantic_ids)):
        errors.append("semantic finding IDs must be unique; aggregate one check's locations in one row")
    if command in COMMAND_IDS:
        for finding_id in semantic_ids:
            if not COMMAND_IDS[command].fullmatch(finding_id):
                errors.append(f"invalid semantic finding ID for {command}: {finding_id}")
        for finding_id in (row["id"] for row in operational_rows):
            if not OPERATIONAL_IDS[command].fullmatch(finding_id):
                errors.append(f"invalid operational finding ID for {command}: {finding_id}")

    for row in rows:
        if row["severity"] not in SEVERITIES:
            errors.append(f"invalid severity for {row['id']}: {row['severity']}")
        if row["disposition"] not in DISPOSITIONS:
            errors.append(f"invalid disposition for {row['id']}: {row['disposition']}")

    routed = [row for row in rows if row["disposition"] == "Route"]
    computed = (
        "BLOCK" if any(row["severity"] in {"CRITICAL", "HIGH"} for row in routed)
        or validation.get("summary", {}).get("exit_code", 0) != 0
        else "ROUTING_REQUIRED" if routed
        else "PASS"
    )
    body_verdict = re.search(r"(?m)^\*\*Verdict\*\*:\s*(\w+)", text)
    if verdict != computed:
        errors.append(f"frontmatter verdict is {verdict!r}; computed verdict is {computed}")
    if not body_verdict or body_verdict.group(1) != computed:
        errors.append(f"body verdict must be {computed}")

    counts = Counter(row["severity"] for row in rows)
    metric = re.search(
        r"Findings by severity:\s*CRITICAL=(\d+)\s*·\s*HIGH=(\d+)\s*·\s*MEDIUM=(\d+)\s*·\s*LOW=(\d+)",
        text,
    )
    expected_counts = tuple(counts[name] for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW"))
    if not metric or tuple(map(int, metric.groups())) != expected_counts:
        errors.append(f"severity metrics must equal {expected_counts}")

    result = {
        "ok": not errors,
        "command": command,
        "verdict": computed,
        "findings": len(rows),
        "counts": dict(counts),
        "validation_errors": errors,
    }
    return result, 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--mechanical", required=True, help="traceability validate --json output file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result, rc = validate(Path(args.report), Path(args.mechanical))
    emit(result)
    return rc


if __name__ == "__main__":
    sys.exit(main())
