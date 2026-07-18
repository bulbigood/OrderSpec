"""Shared workspace and subprocess harness for command-context tests."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
PY = sys.executable
COMMAND_CONTEXT = SCRIPT_DIR.parent / "command_context.py"

if not COMMAND_CONTEXT.exists():
    print(f"FATAL: command_context.py not found at {COMMAND_CONTEXT}", file=sys.stderr)
    sys.exit(2)

LOG_TO_FILE = False

TEST_DIR = SCRIPT_DIR / "test"
TEST_DIR.mkdir(parents=True, exist_ok=True)
LOG = TEST_DIR / "test_command_context.log"

if LOG_TO_FILE:
    LOG.write_text("", encoding="utf-8")

WORK = Path(tempfile.mkdtemp(prefix="orderspec-command-context-test-"))

pass_count = 0
fail_count = 0


def ok(name):
    global pass_count
    pass_count += 1
    msg = f"PASS: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def bad(name):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
    print(msg, flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def reset_work():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def manifest_path():
    return WORK / ".orderspec" / "framework" / "command-context.json"


def put_manifest(data):
    write(manifest_path(), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def run_cc(*args, input_text=None):
    cmd = [PY, str(COMMAND_CONTEXT), "-C", str(WORK)] + list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_cc_json(*args):
    rc, out, err = run_cc(*args)
    try:
        data = json.loads(out)
    except Exception as exc:
        bad(f"invalid JSON output for {' '.join(args)} :: rc={rc} err={err!r} exc={exc} out={out!r}")
        return rc, {}, err
    return rc, data, err


def setup_base_files(
    with_contracts=True,
    with_tooling_protocol=True,
    with_tooling_config=False,
):
    write(WORK / ".orderspec" / "framework" / "orderspec-rules.md", "# Rules\n")
    write(WORK / ".orderspec" / "framework" / "orderspec-identifiers.md", "# IDs\n")
    write(WORK / ".orderspec" / "framework" / "schemas" / "command-context.schema.json", "{}\n")

    if with_tooling_protocol:
        write(
            WORK / ".orderspec" / "framework" / "protocols" / "tooling-protocol.md",
            "# Tooling Protocol\n",
        )
    write(
        WORK / ".orderspec" / "framework" / "protocols" / "sub-agent-execution.md",
        "# Sub-agent Execution\n",
    )
    write(
        WORK / ".orderspec" / "framework" / "protocols" / "environment-block.md",
        "# Environment Block Protocol\n",
    )
    write(
        WORK / ".orderspec" / "framework" / "protocols" / "blocking-feedback.md",
        "# Blocking Feedback Protocol\n",
    )
    write(WORK / ".orderspec" / "framework" / "schemas" / "task-context.schema.json", "{}\n")


    if with_contracts:
        write(WORK / "constitution.md", "# Constitution\n")
        write(WORK / "stack.md", "# Stack\n")
        write(WORK / "architecture.md", "# Architecture\n")
        write(WORK / "conventions.md", "# Conventions\n")
        write(WORK / ".orderspec" / "contracts" / "constitution.md", "# Constitution\n")
        write(WORK / ".orderspec" / "contracts" / "stack.md", "# Stack\n")
        write(WORK / ".orderspec" / "contracts" / "architecture.md", "# Architecture\n")
        write(WORK / ".orderspec" / "contracts" / "conventions.md", "# Conventions\n")

    if with_tooling_config:
        write(WORK / ".orderspec" / "config" / "tooling.json", "{}\n")


def base_manifest():
    return {
        "version": 2,
        "defaults": {
            "required": [
                {
                    "path": ".orderspec/framework/orderspec-rules.md",
                    "kind": "framework_rules",
                    "usage": "apply",
                    "authority": "framework",
                    "reason": "global framework rules",
                },
                {
                    "path": ".orderspec/framework/schemas/command-context.schema.json",
                    "kind": "schema",
                    "usage": "parse",
                    "authority": "framework",
                    "reason": "command context manifest schema",
                },
                {
                    "path": ".orderspec/framework/orderspec-identifiers.md",
                    "kind": "framework_rules",
                    "usage": "apply",
                    "authority": "framework",
                    "reason": "stable identifier prefixes and glossary",
                },
            ]
        },
        "commands": {
            "order.bootstrap": {
                "read_if_exists": [
                    {
                        "path": "constitution.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project governance",
                    },
                    {
                        "path": "stack.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project stack contract",
                    },
                    {
                        "path": "architecture.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project architecture contract",
                    },
                    {
                        "path": "conventions.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "existing project conventions contract",
                    },
                ],
            },
            "order.spec": {
                "required": [
                    {
                        "path": "constitution.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "project governance",
                    }
                ]
            },
            "order.plan": {
                "required": [
                    {
                        "path": ".orderspec/framework/protocols/tooling-protocol.md",
                        "kind": "protocol",
                        "usage": "apply",
                        "authority": "framework",
                        "reason": "tooling protocol",
                    },
                    {
                        "path": "constitution.md",
                        "kind": "project_contract",
                        "usage": "constrain",
                        "authority": "project",
                        "reason": "project governance",
                    },
                ],
                "read_if_exists": [
                    {
                        "path": ".orderspec/config/tooling.json",
                        "kind": "tooling_config",
                        "usage": "parse",
                        "authority": "operator_config",
                        "reason": "tooling config",
                    }
                ],
            },
        },
    }


def paths(data):
    return [item.get("path") for item in data.get("to_read", [])]


def item_by_path(data, path):
    for item in data.get("to_read", []):
        if item.get("path") == path:
            return item
    return None


def missing_required_paths(data):
    return [item.get("path") for item in data.get("missing_required", [])]


def skipped_paths(data):
    return [item.get("path") for item in data.get("skipped_if_missing", [])]


def finish() -> None:
    """Remove the workspace, print the result summary, and exit."""
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)

    print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
    if LOG_TO_FILE:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{pass_count} passed, {fail_count} failed\n")

    raise SystemExit(0 if fail_count == 0 else 1)
