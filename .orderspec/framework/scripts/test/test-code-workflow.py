#!/usr/bin/env python3
"""Regression tests for /order.code deterministic lifecycle preflight."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "code_workflow.py"


def run(root, *args):
    process = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=root,
        env={**os.environ, "ORDERSPEC_ROOT": str(root)},
        capture_output=True,
        text=True,
    )
    return process.returncode, json.loads(process.stdout)


with tempfile.TemporaryDirectory(prefix="orderspec-code-workflow-") as temp:
    root = Path(temp)
    state = root / ".orderspec" / "state"
    feature = root / ".orderspec" / "features" / "001-demo"
    state.mkdir(parents=True)
    feature.mkdir(parents=True)
    (state / "active-feature.json").write_text(json.dumps({
        "feature_id": "FEAT-001-demo",
        "feature_directory": ".orderspec/features/001-demo",
        "status": "planned",
    }), encoding="utf-8")
    (feature / "plan.md").write_text("# Plan\n", encoding="utf-8")

    rc, data = run(root, "preflight", "--mode", "LOCAL_ALL")
    assert rc == 2 and data["error"] == "missing_tasks" and data["route"] == "/order.tasks", data

    rc, data = run(root, "preflight", "--mode", "RESET")
    assert rc == 2 and data["error"] == "missing_tasks", data

    source = root / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (feature / "spec.md").write_text("# Contract\n", encoding="utf-8")
    (feature / "plan.md").write_text(
        "## Physical Project Structure\n\n```pathmanifest\nsrc/service.py [MOD]\n```\n",
        encoding="utf-8",
    )
    (feature / "tasks.md").write_text(
        "# Tasks\n\n"
        "**Format (STRICT — pipe-delimited, machine-parsed)**\n\n"
        "## Task Context (Machine-Readable)\n\n"
        "```task-context\n"
        '{"version":1,"tasks":{"T001":{"read":["src/service.py"],"target_state":"mod"}}}\n'
        "```\n\n---\n\n"
        "## Phase 1\n\n"
        "- [ ] T001 | src/service.py |  | update service\n",
        encoding="utf-8",
    )
    rc, data = run(root, "preflight", "--mode", "LOCAL_ALL")
    assert rc == 0 and data["action"] == "READY" and data["first_unchecked"] == "T001", data
    rc, data = run(
        root,
        "next",
        "--mode",
        "LOCAL_ALL",
        "--feature-dir",
        str(feature),
    )
    assert rc == 0 and data["action"] == "EXECUTE_TASK", data
    packet = data["packets"][0]
    assert packet["task_context"]["write_paths"] == ["src/service.py"], packet

print("All code-workflow tests passed")
