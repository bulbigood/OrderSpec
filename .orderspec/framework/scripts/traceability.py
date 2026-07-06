#!/usr/bin/env python3
"""traceability.py — deterministic source of truth for OrderSpec traceability.

Portable: Python 3 standard library only. No external dependencies.

This script owns machine-readable feature state under:

    <feature-dir>/.state/

It intentionally supports both path models:

1. Legacy basename mode:
      traceability.py -C <repo> init <feature-basename>
      → <repo>/.orderspec/features/<feature-basename>

2. Current OrderSpec:
      SPECIFY_FEATURE_DIRECTORY / .orderspec/state/active-feature.json / --feature-dir
      → arbitrary repo-relative or absolute feature directory

Prompts should prefer the current model. Legacy basename mode is retained for
older tests and prompts.
"""

import argparse
import os
import sys
from pathlib import Path

# ── imports from decomposed modules ──────────────────────────────────────────

from trace_constants import *  # noqa: F401,F403
from trace_tsv import *  # noqa: F401,F403
from trace_parse import *  # noqa: F401,F403
from trace_lint import *  # noqa: F401,F403
from trace_mechanisms import *  # noqa: F401,F403
from trace_validate import *  # noqa: F401,F403

from trace_commands import (
    die, script_dir, resolved_root, set_root, set_feature_dir_override,
    resolve_feature_dir, feature_name, state_dir, state_dir_for_feature_dir,
    spec_path, plan_path, tasks_path,
    cmd_init, cmd_lint, cmd_get,
    cmd_put_mechanisms, cmd_put_spec_ids, cmd_put_trace,
    cmd_extract_spec_ids, cmd_extract_trace,
    cmd_check_plan, cmd_check_mechanisms,
    cmd_suggest_tasks,
    cmd_summarize_mechanisms, cmd_mark_consumed, cmd_diff_summary,
)
from trace_validate import cmd_validate as _cmd_validate
from frontmatter import cmd_validate_frontmatter as _frontmatter_cmd


# ── dispatch ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="traceability.py")
    parser.add_argument("-C", "--root", default=None, help="Path to the project root directory")
    parser.add_argument("--feature-dir", default=None, help="Explicit feature directory path")
    subparsers = parser.add_subparsers(dest="cmd")

    subparsers.add_parser("init", help="init <feature>")
    subparsers.add_parser("lint", help="lint <feature>")
    subparsers.add_parser("extract-spec-ids", help="extract-spec-ids <feature>")
    subparsers.add_parser("extract-trace", help="extract-trace <feature>")
    get_parser = subparsers.add_parser("get", help="get [--feature-dir FD] [feature] <mechanisms|spec-ids|trace>")
    get_parser.add_argument("positional_args", nargs="*")
    pm_parser = subparsers.add_parser("put-mechanisms", help="put-mechanisms <feature>")
    pm_parser.add_argument("--json", action="store_true", help="Read input as JSON array")
    subparsers.add_parser("put-spec-ids", help="put-spec-ids <feature>")
    subparsers.add_parser("put-trace", help="put-trace <feature>")
    st_parser = subparsers.add_parser("suggest-tasks", help="suggest-tasks [--json] <feature>")
    st_parser.add_argument("--json", action="store_true")
    st_parser.add_argument("feature", nargs="?")

    subparsers.add_parser("check-plan", help="check-plan <feature>")
    subparsers.add_parser("check-mechanisms", help="check-mechanisms <feature>")

    sum_parser = subparsers.add_parser("summarize-mechanisms", help="summarize-mechanisms [--json] <feature>")
    sum_parser.add_argument("--json", action="store_true")
    sum_parser.add_argument("feature", nargs="?")

    mc_parser = subparsers.add_parser("mark-consumed", help="mark-consumed --report <path>")
    mc_parser.add_argument("--report", required=True, help="Path to the gate report file to mark as consumed")

    diff_parser = subparsers.add_parser("diff-summary", help="diff-summary --old <ref> [--new <ref>] [--json] <feature>")
    diff_parser.add_argument("--old", required=True, help="Git ref for old version")
    diff_parser.add_argument("--new", default="HEAD", help="Git ref for new version (default: HEAD = working tree)")
    diff_parser.add_argument("--json", action="store_true")
    diff_parser.add_argument("feature", nargs="?")

    val_parser = subparsers.add_parser("validate", help="validate [--json] [--stage] <feature>")
    val_parser.add_argument("--json", action="store_true")
    val_parser.add_argument("--stage", choices=["spec", "plan", "tasks"])
    val_parser.add_argument("feature", nargs="?")

    vfm_parser = subparsers.add_parser("validate-frontmatter", help="validate-frontmatter <type> <file> [--json]")
    vfm_parser.add_argument("--json", action="store_true")
    vfm_parser.add_argument("artifact_type", nargs="?")
    vfm_parser.add_argument("file", nargs="?")

    args, remaining = parser.parse_known_args()

    if args.root:
        set_root(Path(args.root).resolve())
    elif os.environ.get("ORDERSPEC_ROOT"):
        set_root(Path(os.environ["ORDERSPEC_ROOT"]).resolve())
    else:
        cwd = Path.cwd()
        if (cwd / ".orderspec").is_dir():
            set_root(cwd)
        else:
            set_root(script_dir().parent.parent)

    if args.feature_dir:
        set_feature_dir_override(args.feature_dir)

    cmd = args.cmd

    if cmd == "init":
        cmd_init(remaining[0] if remaining else "")
    elif cmd == "lint":
        cmd_lint(remaining[0] if remaining else "")
    elif cmd == "extract-spec-ids":
        cmd_extract_spec_ids(remaining[0] if remaining else "")
    elif cmd == "extract-trace":
        cmd_extract_trace(remaining[0] if remaining else "")
    elif cmd == "suggest-tasks":
        cmd_suggest_tasks(getattr(args, 'feature', None) or (remaining[0] if remaining else ""), json_out=getattr(args, 'json', False))
    elif cmd == "get":
        if len(args.positional_args) == 1:
            cmd_get("", args.positional_args[0])
        elif len(args.positional_args) == 2:
            cmd_get(args.positional_args[0], args.positional_args[1])
        else:
            die("usage: traceability.py get [--feature-dir FD] [feature] <mechanisms|spec-ids|trace>", 64)
    elif cmd == "put-mechanisms":
        cmd_put_mechanisms(remaining[0] if remaining else "", json_input=getattr(args, 'json', False))
    elif cmd == "put-spec-ids":
        cmd_put_spec_ids(remaining[0] if remaining else "")
    elif cmd == "put-trace":
        cmd_put_trace(remaining[0] if remaining else "")
    elif cmd == "check-plan":
        cmd_check_plan(remaining[0] if remaining else "")
    elif cmd == "check-mechanisms":
        cmd_check_mechanisms(remaining[0] if remaining else "")
    elif cmd == "summarize-mechanisms":
        cmd_summarize_mechanisms(args.feature, json_out=args.json)
    elif cmd == "mark-consumed":
        cmd_mark_consumed(args)
    elif cmd == "diff-summary":
        cmd_diff_summary(args)
    elif cmd == "validate":
        _cmd_validate(args)
    elif cmd == "validate-frontmatter":
        _frontmatter_cmd(args, remaining)
    else:
        parser.print_help()
        sys.exit(64)


if __name__ == "__main__":
    main()
