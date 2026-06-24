#!/usr/bin/env python3
"""upstream_gate.py — cascade gate guard.

Deterministic; no LLM judgement. Two checks, in order:
  1. The upstream ARTIFACT must exist — else HARD STOP (exit 2).
  2. If a gate REPORT exists, its verdict must be PASS — else HALT (exit 1).

Output: single JSON line on stdout.
Exit 0 = proceed (status ok | advisory | forced).
Exit 1 = HALT (gate non-PASS, overridable via --force).
Exit 2 = HARD STOP (missing artifact, NOT overridable).

Portable: Python 3 standard library only.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        prog="upstream_gate.py",
        description="Cascade gate guard for OrderSpec pipeline.",
    )
    parser.add_argument("--report", required=False, default="")
    parser.add_argument("--artifact", required=False, default="")
    parser.add_argument("--upstream-name", required=False, default="")
    parser.add_argument("--this", required=False, default="")
    parser.add_argument("--build", required=False, default="")
    parser.add_argument("--fix", required=False, default="")
    parser.add_argument("--recheck", required=False, default="")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def output_json(data):
    """Print a single JSON line to stdout."""
    print(json.dumps(data))


def parse_verdict(report_path):
    """Parse the verdict from a gate report file.
    Looks for a line starting with `**Verdict**:`.
    Returns the verdict string or empty string if not found."""
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("**Verdict**:"):
                    return line[len("**Verdict**:"):].strip()
    except OSError:
        pass
    return ""


def parse_date(report_path):
    """Parse the date from a gate report file.
    Looks for an HTML comment line `<!-- ... · YYYY-MM-DD · ... -->`.
    Returns the date string or 'unknown' if not found."""
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("<!-- "):
                    m = re.search(r"· ([0-9-]*) ·", line)
                    if m:
                        return m.group(1)
                    break
    except OSError:
        pass
    return "unknown"


def main():
    args = parse_args()

    report = args.report
    artifact = args.artifact
    upstream_name = args.upstream_name
    this_cmd = args.this
    build_cmd = args.build
    fix_cmd = args.fix
    recheck_cmd = args.recheck
    force = args.force

    # ── Check 1: the upstream artifact MUST exist. No --force escape. ──
    if not artifact or not Path(artifact).is_file():
        output_json({
            "status": "stop",
            "block": True,
            "reason": "upstream artifact missing",
            "artifact": artifact,
            "upstream_name": upstream_name,
            "this": this_cmd,
            "build": build_cmd,
        })
        sys.exit(2)

    # ── Check 2: the gate report (optional) ──
    if not report or not Path(report).is_file():
        output_json({
            "status": "advisory",
            "block": False,
            "reason": f"upstream gate ({recheck_cmd}) was not run",
            "recheck": recheck_cmd,
        })
        sys.exit(0)

    verdict = parse_verdict(report)
    date = parse_date(report)

    if "PASS" in verdict:
        # Check if artifact is newer than report (stale)
        try:
            artifact_mtime = Path(artifact).stat().st_mtime
            report_mtime = Path(report).stat().st_mtime
            if artifact_mtime > report_mtime:
                output_json({
                    "status": "advisory",
                    "block": False,
                    "verdict": "PASS",
                    "reason": "artifact changed after last PASS (stale)",
                    "recheck": recheck_cmd,
                })
                sys.exit(0)
        except OSError:
            pass
        output_json({
            "status": "ok",
            "block": False,
            "verdict": "PASS",
        })
        sys.exit(0)

    elif "ROUTING" in verdict or "BLOCK" in verdict:
        if force:
            output_json({
                "status": "forced",
                "block": False,
                "verdict": verdict,
                "date": date,
            })
            sys.exit(0)
        output_json({
            "status": "halt",
            "block": True,
            "verdict": verdict,
            "date": date,
            "this": this_cmd,
            "fix": fix_cmd,
            "recheck": recheck_cmd,
        })
        sys.exit(1)

    else:
        # Unparseable verdict
        if force:
            output_json({
                "status": "forced",
                "block": False,
                "verdict": "unparseable",
            })
            sys.exit(0)
        output_json({
            "status": "halt",
            "block": True,
            "verdict": "unparseable",
            "this": this_cmd,
            "fix": fix_cmd,
            "recheck": recheck_cmd,
        })
        sys.exit(1)


if __name__ == "__main__":
    main()