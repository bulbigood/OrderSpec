#!/usr/bin/env python3
"""setup.py — consolidated prerequisite checking and setup for OrderSpec.

Replaces:
  - setup-plan.sh       → `setup.py plan`
  - setup-tasks.sh      → `setup.py tasks`
  - check-prerequisites → `setup.py code`

All output intended for prompt consumption is JSON on stdout.
Informational/diagnostic messages go to stderr.

Portable: Python 3 standard library only.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# Import shared functions and canonical paths from common.py (same directory)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    ACTIVE_FEATURE_STATE,
    FRAMEWORK_TEMPLATES_DIR,
    PRESETS_DIR,
    TEMPLATE_OVERRIDES_DIR,
    get_feature_paths,
    resolve_template,
)


TASKS_TEMPLATE_NAME = "tasks-template"
PLAN_TEMPLATE_NAME = "plan-template"

TASKS_TEMPLATE_FILE = f"{TASKS_TEMPLATE_NAME}.md"
PLAN_TEMPLATE_FILE = f"{PLAN_TEMPLATE_NAME}.md"


def output_json(data):
    """Print a single JSON object to stdout."""
    print(json.dumps(data))

def output_result(data, args):
    """Print result as JSON or eval-ready shell variables."""
    if getattr(args, "shell_vars", False):
        for key, value in data.items():
            if isinstance(value, str):
                print(f'{key}="{value}"')
        return
    output_json(data)


def die(msg, rc=1):
    """Print error to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(rc)


def collect_available_docs(paths, include_tasks=False):
    """Build a list of available optional documents in the feature directory."""
    docs = []

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


def base_paths_payload(paths):
    """Return the common JSON payload for resolved feature paths.

    `FEATURE_DIR` is the canonical key.
    `SPECS_DIR` is retained as a deprecated compatibility alias for older prompts.
    """
    feature_dir_name = Path(paths["FEATURE_DIR"]).name
    feature_id = f"FEAT-{feature_dir_name}" if not feature_dir_name.startswith("FEAT-") else feature_dir_name
    
    return {
        "REPO_ROOT": paths["REPO_ROOT"],
        "CURRENT_BRANCH": paths["CURRENT_BRANCH"],
        "BRANCH": paths["CURRENT_BRANCH"],
        "FEATURE_ID": feature_id,
        "FEATURE_DIR": paths["FEATURE_DIR"],
        "SPECS_DIR": paths["FEATURE_DIR"],  # deprecated alias
        "FEATURE_SPEC": paths["FEATURE_SPEC"],
        "IMPL_PLAN": paths["IMPL_PLAN"],
        "TASKS": paths["TASKS"],
        "DATA_MODEL": paths["DATA_MODEL"],
        "QUICKSTART": paths["QUICKSTART"],
        "CONTRACTS_DIR": paths["CONTRACTS_DIR"],
    }


# ── subcommand: paths ────────────────────────────────────────────────────────

def cmd_paths(args):
    """Resolve active feature paths without creating or modifying files.

    This command is intentionally read-only. It is safe to run before gates.
    It requires the active feature directory to be resolvable from either:
      - SPECIFY_FEATURE_DIRECTORY
      - `.orderspec/state/active-feature.json`

    It does NOT require spec.md, plan.md, or tasks.md to exist.
    """
    try:
        paths = get_feature_paths(persist_active_feature=False)
    except RuntimeError as e:
        die(str(e), rc=2)

    payload = base_paths_payload(paths)
    payload.update({
        "FEATURE_DIR_EXISTS": Path(paths["FEATURE_DIR"]).is_dir(),
        "SPEC_EXISTS": Path(paths["FEATURE_SPEC"]).is_file(),
        "PLAN_EXISTS": Path(paths["IMPL_PLAN"]).is_file(),
        "TASKS_EXISTS": Path(paths["TASKS"]).is_file(),
    })
    
    output_result(payload, args)


# ── subcommand: plan ─────────────────────────────────────────────────────────

def cmd_plan(args):
    """Setup for /order.plan — validate spec, create/copy plan template, output paths.

    Safety contract:
      - plan.md is derived from spec.md, so spec.md MUST exist first.
      - By default, an existing plan.md is preserved for compatibility.
      - With --refresh-template, plan.md is regenerated from the currently
        resolved template before the prompt fills it.
    """
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e), rc=2)

    feature_dir = Path(paths["FEATURE_DIR"])
    feature_spec = Path(paths["FEATURE_SPEC"])
    impl_plan = Path(paths["IMPL_PLAN"])
    repo_root = paths["REPO_ROOT"]

    # A plan cannot be produced without a contract.
    if not feature_spec.is_file():
        die(
            f"spec.md not found: {feature_spec}\n"
            f"Run /order.spec first to create the feature contract.",
            rc=2,
        )

    # Ensure feature directory exists. If spec.md exists, this should already be true,
    # but keeping mkdir makes the command robust to unusual filesystems.
    feature_dir.mkdir(parents=True, exist_ok=True)

    template = resolve_template(PLAN_TEMPLATE_NAME, repo_root)

    if impl_plan.is_file() and not args.refresh_template:
        print(
            f"Plan already exists at {impl_plan}, skipping template copy "
            f"(use --refresh-template to regenerate)",
            file=sys.stderr,
        )
    else:
        if template and Path(template).is_file():
            shutil.copy2(template, impl_plan)
            if args.refresh_template and impl_plan.is_file():
                print(f"Refreshed plan template at {impl_plan}", file=sys.stderr)
            else:
                print(f"Copied plan template to {impl_plan}", file=sys.stderr)
        else:
            print("Warning: Plan template not found; creating empty plan.md", file=sys.stderr)
            impl_plan.touch()

    payload = base_paths_payload(paths)
    payload.update({
        "PLAN_TEMPLATE": template or "",
        "PLAN_REFRESHED": bool(args.refresh_template),
    })
    output_result(payload, args)


# ── subcommand: tasks ────────────────────────────────────────────────────────

def cmd_tasks(args):
    """Setup for /order.tasks — validate spec+plan, collect docs, resolve tasks template."""
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e), rc=2)

    feature_spec = paths["FEATURE_SPEC"]
    impl_plan = paths["IMPL_PLAN"]
    repo_root = paths["REPO_ROOT"]

    # Validate required files
    if not Path(impl_plan).is_file():
        die(
            f"plan.md not found in {paths['FEATURE_DIR']}\n"
            f"Run /order.plan first to create the implementation plan.",
            rc=2,
        )

    if not Path(feature_spec).is_file():
        die(
            f"spec.md not found in {paths['FEATURE_DIR']}\n"
            f"Run /order.spec first to create the feature structure.",
            rc=2,
        )

    # Build available docs list
    docs = collect_available_docs(paths, include_tasks=False)

    # Resolve tasks template through the supported template stack
    tasks_template = resolve_template(TASKS_TEMPLATE_NAME, repo_root)
    if not tasks_template or not Path(tasks_template).is_file():
        override_path = TEMPLATE_OVERRIDES_DIR / TASKS_TEMPLATE_FILE
        core_path = FRAMEWORK_TEMPLATES_DIR / TASKS_TEMPLATE_FILE

        die(
            f"Could not resolve required {TASKS_TEMPLATE_NAME} from the template "
            f"resolution stack for {repo_root}\n"
            f"Template '{TASKS_TEMPLATE_NAME}' was not found in any supported location "
            f"(project overrides, presets, or framework core). Add an override "
            f"at {override_path}, or run 'orderspec init' / reinstall shared infra "
            f"to restore the core {core_path} template.",
            rc=2,
        )

    output_json({
        "FEATURE_DIR": paths["FEATURE_DIR"],
        "AVAILABLE_DOCS": docs,
        "TASKS_TEMPLATE": tasks_template,
    })


# ── subcommand: code ─────────────────────────────────────────────────────────

def cmd_code(args):
    """Setup for /order.code — validate feature dir + plan + tasks, collect docs."""
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e), rc=2)

    feature_dir = paths["FEATURE_DIR"]
    impl_plan = paths["IMPL_PLAN"]
    tasks = paths["TASKS"]

    # Validate required directories and files
    if not Path(feature_dir).is_dir():
        die(
            f"Feature directory not found: {feature_dir}\n"
            f"Run /order.spec first to create the feature structure.",
            rc=2,
        )

    if not Path(impl_plan).is_file():
        die(
            f"plan.md not found in {feature_dir}\n"
            f"Run /order.plan first to create the implementation plan.",
            rc=2,
        )

    if not Path(tasks).is_file():
        die(
            f"tasks.md not found in {feature_dir}\n"
            f"Run /order.tasks first to create the task list.",
            rc=2,
        )

    # Build available docs list (including tasks.md)
    docs = collect_available_docs(paths, include_tasks=True)

    output_json({
        "FEATURE_DIR": feature_dir,
        "AVAILABLE_DOCS": docs,
    })


# ── subcommand: spec ─────────────────────────────────────────────────────────

def cmd_spec(args):
    """Setup for /order.spec — validate feature dir exists, output paths.

    This command is intentionally stricter than `paths`: it is used when the
    spec author/refiner expects an existing feature directory.
    """
    try:
        paths = get_feature_paths()
    except RuntimeError as e:
        die(str(e), rc=2)

    feature_dir = Path(paths["FEATURE_DIR"])
    feature_spec = Path(paths["FEATURE_SPEC"])

    # Feature directory must exist (created by /order.spec)
    if not feature_dir.is_dir():
        die(
            f"Feature directory not found: {feature_dir}\n"
            f"Run /order.spec first to create the feature structure.",
            rc=2,
        )

    # spec.md may or may not exist yet (first run vs refinement)
    spec_exists = feature_spec.is_file()

    output_json({
        "FEATURE_DIR": paths["FEATURE_DIR"],
        "FEATURE_SPEC": paths["FEATURE_SPEC"],
        "SPEC_EXISTS": spec_exists,
        "REPO_ROOT": paths["REPO_ROOT"],
        "ACTIVE_FEATURE_STATE": str(ACTIVE_FEATURE_STATE),
    })


# ── dispatch ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="Consolidated prerequisite checking and setup for OrderSpec.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    paths_parser = subparsers.add_parser(
        "paths",
        help="Resolve active feature paths without creating/modifying files",
    )
    paths_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON (always on)",
    )
    paths_parser.add_argument(
        "--shell-vars",
        action="store_true",
        help="Output as eval-ready shell variable assignments",
    )

    spec_parser = subparsers.add_parser("spec", help="Setup for /order.spec")
    spec_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON (always on)",
    )
    spec_parser.add_argument(
        "--shell-vars",
        action="store_true",
        help="Output as eval-ready shell variable assignments",
    )

    plan_parser = subparsers.add_parser("plan", help="Setup for /order.plan")
    plan_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON (always on)",
    )
    plan_parser.add_argument(
        "--shell-vars",
        action="store_true",
        help="Output as eval-ready shell variable assignments",
    )
    plan_parser.add_argument(
        "--refresh-template",
        action="store_true",
        help="Regenerate plan.md from the resolved plan template even if it already exists",
    )

    tasks_parser = subparsers.add_parser("tasks", help="Setup for /order.tasks")
    tasks_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON (always on)",
    )
    tasks_parser.add_argument(
        "--shell-vars",
        action="store_true",
        help="Output as eval-ready shell variable assignments",
    )

    code_parser = subparsers.add_parser("code", help="Setup for /order.code")
    code_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON (always on)",
    )
    code_parser.add_argument(
        "--shell-vars",
        action="store_true",
        help="Output as eval-ready shell variable assignments",
    )

    args = parser.parse_args()

    if args.cmd == "paths":
        cmd_paths(args)
    elif args.cmd == "spec":
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