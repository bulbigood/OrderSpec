#!/usr/bin/env python3
"""Deterministically validate a completed /order.code-check report."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frontmatter import extract_yaml_frontmatter, validate_gate_report_frontmatter  # noqa: E402


REQUIRED_HEADINGS = (
    "## Code Check (implementation — code ↔ contract)",
    "### Assurance Limits",
    "### Routing Required",
    "### Findings",
    "### Coverage Exceptions",
    "### Evidence Execution",
    "### Metrics",
)
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
RESULTS = {"VIOLATED", "UNPROVEN"}
DISPOSITIONS = {"Route", "Advisory", "Accepted"}
FINDING_ID_RE = re.compile(r"^C[0-5]-[0-9a-f]{8}$")
PLACEHOLDER_RE = re.compile(
    r"\{(?:[A-Z][A-Z0-9_]*|[a-z][a-z0-9_]*(?:_rows|_count|_routes|_state|_limits|_assessed|_path|_summary))\}"
)
SEVERITY_METRICS_RE = re.compile(
    r"Findings by severity: CRITICAL=(\d+) · HIGH=(\d+) · MEDIUM=(\d+) · LOW=(\d+)"
)


def section(text, heading):
    start = text.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    next_heading = re.search(r"\n#{2,3} ", text[start:])
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


def parse_findings(text, errors):
    body = section(text, "### Findings")
    findings = []
    seen_ids = set()
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if not cells or cells[0] in {"ID", "----", "(none)", "{findings_rows}"}:
            continue
        if set(cells[0]) == {"-"}:
            continue
        if len(cells) != 8:
            errors.append({"field": "findings", "message": f"finding row must have 8 columns: {line}"})
            continue
        finding_id, _, severity, result, disposition, owner, _, _ = cells
        if not FINDING_ID_RE.fullmatch(finding_id):
            errors.append({"field": "findings.id", "message": f"invalid stable finding ID: {finding_id}"})
        elif finding_id in seen_ids:
            errors.append({"field": "findings.id", "message": f"duplicate finding ID: {finding_id}"})
        seen_ids.add(finding_id)
        if severity not in SEVERITIES:
            errors.append({"field": "findings.severity", "message": f"invalid severity for {finding_id}: {severity}"})
        if result not in RESULTS:
            errors.append({"field": "findings.result", "message": f"invalid result for {finding_id}: {result}"})
        if disposition not in DISPOSITIONS:
            errors.append({"field": "findings.disposition", "message": f"invalid disposition for {finding_id}: {disposition}"})
        if disposition == "Route" and not owner.startswith("/order."):
            errors.append({"field": "findings.owner", "message": f"routed finding {finding_id} needs an /order.* owner"})
        findings.append({"id": finding_id, "severity": severity, "result": result, "disposition": disposition})
    return findings


def validate(path):
    text = path.read_text(encoding="utf-8")
    errors = [
        {"field": field, "message": message}
        for field, message in validate_gate_report_frontmatter(text)
    ]
    fm = extract_yaml_frontmatter(text).get("orderspec", {})

    if fm.get("command") != "order.code-check":
        errors.append({"field": "orderspec.command", "message": "code report command must be order.code-check"})
    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            errors.append({"field": "body", "message": f"missing required heading: {heading}"})
    for match in sorted(set(PLACEHOLDER_RE.findall(text))):
        errors.append({"field": "body", "message": f"unresolved template placeholder: {match}"})

    findings = parse_findings(text, errors)
    routed = [item for item in findings if item["disposition"] == "Route"]
    routing_body = section(text, "### Routing Required")
    for item in routed:
        if item["id"] not in routing_body:
            errors.append({
                "field": "routing",
                "message": f"routed finding {item['id']} is not referenced in Routing Required",
            })

    metrics_match = SEVERITY_METRICS_RE.search(section(text, "### Metrics"))
    if not metrics_match:
        errors.append({"field": "metrics", "message": "missing Findings by severity metrics"})
    else:
        reported = dict(zip(("CRITICAL", "HIGH", "MEDIUM", "LOW"), map(int, metrics_match.groups())))
        actual = {severity: 0 for severity in SEVERITIES}
        for item in findings:
            if item["severity"] in actual:
                actual[item["severity"]] += 1
        if reported != actual:
            errors.append({
                "field": "metrics",
                "message": f"severity metrics {reported} do not match findings {actual}",
            })
    terminal = fm.get("terminal_precondition") is True
    if terminal or any(item["severity"] in {"CRITICAL", "HIGH"} for item in routed):
        expected = "BLOCK"
    elif routed:
        expected = "ROUTING_REQUIRED"
    else:
        expected = "PASS"
    if fm.get("verdict") != expected:
        errors.append({
            "field": "orderspec.verdict",
            "message": f"verdict {fm.get('verdict')} does not match deterministic verdict {expected}",
        })
    if f"**Verdict**: {fm.get('verdict')}" not in text:
        errors.append({"field": "body.verdict", "message": "body verdict must match frontmatter verdict"})
    if f"**Assurance**: {fm.get('assurance')}" not in text:
        errors.append({"field": "body.assurance", "message": "body assurance must match frontmatter assurance"})

    return {
        "ok": not errors,
        "file": str(path),
        "verdict": fm.get("verdict"),
        "assurance": fm.get("assurance"),
        "findings": len(findings),
        "routed": len(routed),
        "errors": errors,
    }


def finding_id(pass_name, owner, obligation, location):
    canonical = "\x1f".join(
        value.strip().lower() for value in (pass_name, owner, obligation, location)
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return f"{pass_name.upper()}-{digest}"


def finalize(path):
    result = validate(path)
    if not result["ok"]:
        return result, 1

    fm = extract_yaml_frontmatter(path.read_text(encoding="utf-8"))["orderspec"]
    status = "verified" if fm["verdict"] == "PASS" else "blocked"
    active_feature = Path(__file__).resolve().parent / "active_feature.py"
    process = subprocess.run(
        [
            sys.executable,
            str(active_feature),
            "set",
            "--feature-id",
            str(fm["feature_id"]),
            "--feature-directory",
            str(fm["feature_directory"]),
            "--status",
            status,
            "--last-command",
            "order.code-check",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        result["ok"] = False
        result["errors"].append({
            "field": "active_feature",
            "message": process.stderr.strip() or process.stdout.strip() or "status update failed",
        })
        return result, process.returncode

    result["active_feature_status"] = status
    try:
        result["active_feature"] = json.loads(process.stdout)
    except json.JSONDecodeError:
        result["active_feature"] = process.stdout.strip()
    return result, 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "finding-id":
        parser = argparse.ArgumentParser(description="Create a stable code-check finding ID")
        parser.add_argument("finding-id")
        parser.add_argument("--pass", dest="pass_name", required=True, choices=[f"C{i}" for i in range(6)])
        parser.add_argument("--owner", required=True)
        parser.add_argument("--obligation", required=True)
        parser.add_argument("--location", required=True)
        args = parser.parse_args()
        print(finding_id(args.pass_name, args.owner, args.obligation, args.location))
        return 0

    if len(sys.argv) > 1 and sys.argv[1] == "finalize":
        parser = argparse.ArgumentParser(description="Validate a code report and apply its derived feature status")
        parser.add_argument("finalize")
        parser.add_argument("report")
        parser.add_argument("--json", action="store_true")
        args = parser.parse_args()
        path = Path(args.report)
        if not path.is_file():
            result = {"ok": False, "errors": [{"field": "file", "message": "report not found"}]}
            print(json.dumps(result))
            return 2
        result, rc = finalize(path)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for error in result["errors"]:
                print(f"{error['field']}: {error['message']}")
        return rc

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    path = Path(args.report)
    if not path.is_file():
        print(json.dumps({"ok": False, "errors": [{"field": "file", "message": "report not found"}]}))
        return 2
    result = validate(path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for error in result["errors"]:
            print(f"{error['field']}: {error['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
