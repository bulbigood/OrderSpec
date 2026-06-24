#!/usr/bin/env python3
"""setup.py — consolidated prerequisite checking and setup for OrderSpec.

Replaces:
  - setup-plan.sh       → `setup.py plan`
  - setup-tasks.sh      → `setup.py tasks`
  - check-prerequisites → `setup.py code`

All output is JSON on stdout; informational/diagnostic messages go to stderr.

Portable: Python 3 standard library only.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Import shared functions from common.py (same directory)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import get_feature_paths, resolve_template


def output_json(data):
    """Print a single JSON line to stdout."""
    print(json.dumps(data))


def die(msg, rc=1):
    """Print error to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(rc)


def collect_available_docs(paths, include_tasks=False):
    """Build a list of available optional documents in the feature directory."""
    docs = []

    if Path(paths["RESEARCH"]).is_file():
        docs.append("research.md")

    if Path(paths["DATA_MODEL"]).is_file():
        docs.append("data-model.md")

    contracts_dir = Path(paths["CONTRACTS_DIR"])
    if contracts_dir.is_dir():
        try:
            if any(contracts_dir.iterdir()):
                docs.append("contracts/")
        except OSError:
            pass

    if Path(paths["QUICKSTART"]).is_file():
        docs.append("quickstart.md")

    if include_tasks and Path(paths["TASKS"]).is_file():
        docs.append("tasks.md")

    return docs


# ── subcommand: plan ─────────────────────────────────────────────────────────

def cmd_plan(args):
    """Setup for /order.plan — create feature dir, copy plan template, output paths."""
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e))

    feature_dir = Path(paths["FEATURE_DIR"])
    impl_plan = Path(paths["IMPL_PLAN"])
    repo_root = paths["REPO_ROOT"]

    # Ensure feature directory exists
    feature_dir.mkdir(parents=True, exist_ok=True)

    # Copy plan template if plan doesn't already exist
    if impl_plan.is_file():
        print(f"Plan already exists at {impl_plan}, skipping template copy",
              file=sys.stderr)
    else:
        template = resolve_template("plan-template", repo_root)
        if template and Path(template).is_file():
            shutil.copy2(template, impl_plan)
            print(f"Copied plan template to {impl_plan}", file=sys.stderr)
        else:
            print("Warning: Plan template not found", file=sys.stderr)
            impl_plan.touch()

    output_json({
        "FEATURE_SPEC": paths["FEATURE_SPEC"],
        "IMPL_PLAN": paths["IMPL_PLAN"],
        "SPECS_DIR": paths["FEATURE_DIR"],
        "BRANCH": paths["CURRENT_BRANCH"],
    })


# ── subcommand: tasks ────────────────────────────────────────────────────────

def cmd_tasks(args):
    """Setup for /order.tasks — validate spec+plan, collect docs, resolve tasks template."""
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e))

    feature_spec = paths["FEATURE_SPEC"]
    impl_plan = paths["IMPL_PLAN"]
    repo_root = paths["REPO_ROOT"]

    # Validate required files
    if not Path(impl_plan).is_file():
        die(f"plan.md not found in {paths['FEATURE_DIR']}\n"
            f"Run /order.plan first to create the implementation plan.")

    if not Path(feature_spec).is_file():
        die(f"spec.md not found in {paths['FEATURE_DIR']}\n"
            f"Run /order.spec first to create the feature structure.")

    # Build available docs list
    docs = collect_available_docs(paths, include_tasks=False)

    # Resolve tasks template through override stack
    tasks_template = resolve_template("tasks-template", repo_root)
    if not tasks_template or not Path(tasks_template).is_file():
        die(
            f"Could not resolve required tasks-template from the template "
            f"override stack for {repo_root}\n"
            f"Template 'tasks-template' was not found in any supported location "
            f"(overrides, presets, extensions, or shared core). Add an override "
            f"at .orderspec/templates/overrides/tasks-template.md, or run "
            f"'orderspec init' / reinstall shared infra to restore the core "
            f".orderspec/templates/tasks-template.md template."
        )

    output_json({
        "FEATURE_DIR": paths["FEATURE_DIR"],
        "AVAILABLE_DOCS": docs,
        "TASKS_TEMPLATE": tasks_template or "",
    })


# ── subcommand: code ─────────────────────────────────────────────────────────

def cmd_code(args):
    """Setup for /order.code — validate feature dir + plan + tasks, collect docs."""
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e))

    feature_dir = paths["FEATURE_DIR"]
    impl_plan = paths["IMPL_PLAN"]
    tasks = paths["TASKS"]

    # Validate required directories and files
    if not Path(feature_dir).is_dir():
        die(f"Feature directory not found: {feature_dir}\n"
            f"Run /order.spec first to create the feature structure.")

    if not Path(impl_plan).is_file():
        die(f"plan.md not found in {feature_dir}\n"
            f"Run /order.plan first to create the implementation plan.")

    if not Path(tasks).is_file():
        die(f"tasks.md not found in {feature_dir}\n"
            f"Run /order.tasks first to create the task list.")

    # Build available docs list (including tasks.md)
    docs = collect_available_docs(paths, include_tasks=True)

    output_json({
        "FEATURE_DIR": feature_dir,
        "AVAILABLE_DOCS": docs,
    })


# ── subcommand: spec ─────────────────────────────────────────────────────────

def cmd_spec(args):
    """Setup for /order.spec — validate feature dir exists, output paths."""
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e))

    feature_dir = Path(paths["FEATURE_DIR"])
    feature_spec = Path(paths["FEATURE_SPEC"])

    # Feature directory must exist (created by /order.spec)
    if not feature_dir.is_dir():
        die(f"Feature directory not found: {feature_dir}\n"
            f"Run /order.spec first to create the feature structure.")

    # spec.md may or may not exist yet (first run vs refinement)
    spec_exists = feature_spec.is_file()

    output_json({
        "FEATURE_DIR": paths["FEATURE_DIR"],
        "FEATURE_SPEC": paths["FEATURE_SPEC"],
        "SPEC_EXISTS": spec_exists,
        "REPO_ROOT": paths["REPO_ROOT"],
    })

# ── dispatch ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="Consolidated prerequisite checking and setup for OrderSpec.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    spec_parser = subparsers.add_parser("spec", help="Setup for /order.spec")
    spec_parser.add_argument("--json", action="store_true", help="Output in JSON (always on)")

    plan_parser = subparsers.add_parser("plan", help="Setup for /order.plan")
    plan_parser.add_argument("--json", action="store_true", help="Output in JSON (always on)")

    tasks_parser = subparsers.add_parser("tasks", help="Setup for /order.tasks")
    tasks_parser.add_argument("--json", action="store_true", help="Output in JSON (always on)")

    code_parser = subparsers.add_parser("code", help="Setup for /order.code")
    code_parser.add_argument("--json", action="store_true", help="Output in JSON (always on)")

    args = parser.parse_args()

    if args.cmd == "spec":
        cmd_spec(args)
    elif args.cmd == "plan":
        cmd_plan(args)
    elif args.cmd == "tasks":
        cmd_tasks(args)
    elif args.cmd == "code":
        cmd_code(args)
    else:
        parser.print_help()
        sys.exit(64)


if __name__ == "__main__":
    main()