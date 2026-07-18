#!/usr/bin/env python3
"""upstream_gate.py — cascade gate guard.

Deterministic; no LLM judgement. Checks, in order:

  0. Invocation sanity: required path arguments must not be empty.
  1. The upstream ARTIFACT must exist — else HARD STOP (exit 2).
  2. A CONSUMED_STALE report is inactive — proceed with advisory (exit 0).
  3. Otherwise, if a gate REPORT exists, its verdict must be PASS — else HALT
     (exit 1).

Output: single JSON line on stdout.

Exit 0  = proceed (status ok | advisory | forced).
Exit 1  = HALT (gate non-PASS, overridable via --force).
Exit 2  = HARD STOP (missing artifact, NOT overridable).
Exit 64 = invocation error (usually empty shell variable).
"""

import argparse
import json
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


def empty_arg(value):
    return value is None or str(value).strip() == ""


def looks_like_unset_var(path):
    """Detect paths like '/plan.md' that result from empty shell variables.

    When an LLM forgets to run `eval "$(setup.py paths --shell-vars)"` or
    the shell session resets, variables like $FEATURE_DIR expand to empty.
    This turns "$FEATURE_DIR/plan.md" into "/plan.md", which is a root-level
    path and almost certainly an invocation error, not a real file.
    """
    return bool(re.match(r'^/[a-zA-Z0-9_.-]+$', path))


def parse_verdict(report_path):
    """Parse the verdict from a gate report file.

    Looks for a line starting with `**Verdict**:`.
    Returns the verdict string or empty string if not found.
    Uses .strip() before startswith to tolerate leading
    whitespace in Markdown output.
    """
    marker = "**Verdict**:"
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(marker):
                    return stripped[len(marker):].strip()
    except OSError:
        pass
    return ""


def report_is_consumed_stale(report_path):
    """Recognize current and legacy canonical mark-consumed output.

    A missing verdict alone is not enough: malformed reports must remain
    fail-closed instead of being mistaken for consumed workflow state.
    """
    marker = "<!-- orderspec-report-state: CONSUMED_STALE -->"
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped == marker or stripped.startswith("# CONSUMED_STALE — "):
                    return True
            return False
    except OSError:
        return False


def parse_date(report_path):
    """Parse the date from a gate report file.

    Looks for an HTML comment line `<!-- ... · YYYY-MM-DD · ... -->`.
    Returns the date string or 'unknown' if not found.
    Uses .strip() before startswith to tolerate leading
    whitespace in Markdown output.
    """
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("<!-- "):
                    m = re.search(r"· ([0-9\-]*) ·", stripped)
                    if m:
                        return m.group(1)
                    break
    except OSError:
        pass
    return "unknown"


def verdict_is_pass(verdict):
    """Return True only for an explicit PASS verdict.

    Do not use substring `PASS in verdict`: strings like `NOT PASS` or
    stale marker prose must not be interpreted as successful gates.
    """
    v = verdict.strip().upper()
    return v in {"PASS", "✅ PASS"} or v.startswith("✅ PASS")


def verdict_is_nonpass(verdict):
    v = verdict.strip().upper()
    return (
        "ROUTING" in v
        or "BLOCK" in v
        or v.startswith("🔀")
        or v.startswith("⛔")
    )


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

    # ── Check 0: invocation sanity ───────────────────────────────────────────
    # Empty path arguments usually mean the prompt relied on shell variables
    # that did not persist across tool invocations. Report that directly.
    if empty_arg(artifact):
        output_json({
            "status": "error",
            "block": True,
            "reason": "empty --artifact argument; shell variables may not be initialized",
            "artifact": "",
            "upstream_name": upstream_name,
            "this": this_cmd,
            "build": build_cmd,
        })
        sys.exit(64)

    if empty_arg(report):
        output_json({
            "status": "error",
            "block": True,
            "reason": "empty --report argument; shell variables may not be initialized",
            "report": "",
            "upstream_name": upstream_name,
            "this": this_cmd,
            "recheck": recheck_cmd,
        })
        sys.exit(64)

    # Catch paths like "/plan.md" that result from unset $FEATURE_DIR.
    # This happens when the LLM forgets to eval the shell-vars output.
    if looks_like_unset_var(artifact):
        output_json({
            "status": "error",
            "block": True,
            "reason": "artifact path looks like an unset shell variable expanded to root (e.g. /plan.md). Did you forget to run `eval \"$(setup.py paths --shell-vars)\"`?",
            "artifact": artifact,
            "upstream_name": upstream_name,
            "this": this_cmd,
            "build": build_cmd,
        })
        sys.exit(64)

    if looks_like_unset_var(report):
        output_json({
            "status": "error",
            "block": True,
            "reason": "report path looks like an unset shell variable expanded to root (e.g. /spec-report.md). Did you forget to run `eval \"$(setup.py paths --shell-vars)\"`?",
            "report": report,
            "upstream_name": upstream_name,
            "this": this_cmd,
            "recheck": recheck_cmd,
        })
        sys.exit(64)

    # ── Check 1: the upstream artifact MUST exist. No --force escape. ────────
    if not Path(artifact).is_file():
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

    # ── Check 2: the gate report is optional ─────────────────────────────────
    if not Path(report).is_file():
        output_json({
            "status": "advisory",
            "block": False,
            "reason": f"upstream gate ({recheck_cmd}) was not run",
            "recheck": recheck_cmd,
        })
        sys.exit(0)

    if report_is_consumed_stale(report):
        output_json({
            "status": "advisory",
            "block": False,
            "state": "consumed_stale",
            "reason": "upstream gate report was consumed; fresh verdict not available",
            "recheck": recheck_cmd,
        })
        sys.exit(0)

    verdict = parse_verdict(report)
    date = parse_date(report)

    if verdict_is_pass(verdict):
        # Check if artifact is newer than report (stale PASS).
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

    if verdict_is_nonpass(verdict):
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

    # Unparseable verdict.
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
