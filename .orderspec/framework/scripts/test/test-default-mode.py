#!/usr/bin/env python3
"""Regression tests for argument-free command mode selection."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "default_mode.py"


def run(root: Path, command: str, feature: Path | None = None, semantic: str = ""):
    args = [sys.executable, str(SCRIPT), "resolve", "--command", command, "--semantic-input", semantic]
    if feature is not None:
        args.extend(["--feature-dir", str(feature)])
    process = subprocess.run(args, cwd=root, env={**os.environ, "ORDERSPEC_ROOT": str(root)}, capture_output=True, text=True)
    return process.returncode, json.loads(process.stdout)


with tempfile.TemporaryDirectory(prefix="orderspec-default-mode-") as temp:
    root = Path(temp)
    feature = root / ".orderspec" / "features" / "001-demo"
    feedback_dir = feature / ".state" / "feedback"
    feedback_dir.mkdir(parents=True)

    rc, data = run(root, "order.spec", feature)
    assert rc == 0 and data["action"] == "ASK" and data["ask_user"], data

    (feature / "spec.md").write_text("# Spec\n", encoding="utf-8")
    rc, data = run(root, "order.spec", feature)
    assert rc == 0 and data["mode"] == "REFINE" and not data["ask_user"], data

    feedback = {
        "version": 1,
        "id": "FB-001",
        "status": "open",
        "source": "order.code",
        "target": "order.spec",
    }
    (feedback_dir / "FB-001.json").write_text(json.dumps(feedback), encoding="utf-8")
    rc, data = run(root, "order.spec", feature)
    assert data["mode"] == "REFINE" and data["open_feedback"] == ["FB-001"], data

    rc, data = run(root, "order.plan", feature)
    assert data["mode"] == "GENERATE", data
    (feature / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature / "tasks.md").write_text("- [X] T001 | a |  | done\n- [ ] T002 | b | REQ-001 | todo\n", encoding="utf-8")
    time.sleep(0.002)
    (feature / "spec.md").write_text("# Refined spec\n", encoding="utf-8")
    rc, data = run(root, "order.plan", feature)
    assert data["mode"] == "RECONCILE" and data["upstream_newer"], data
    assert data["completed_tasks"] == 1 and data["classify_impact_before_write"], data

    rc, data = run(root, "order.tasks", feature)
    assert data["mode"] == "REFINE" and data["upstream_newer"], data
    time.sleep(0.002)
    tasks_content = (feature / "tasks.md").read_text(encoding="utf-8")
    (feature / "tasks.md").write_text(tasks_content, encoding="utf-8")
    rc, data = run(root, "order.tasks", feature)
    assert data["mode"] == "INSPECT" and data["completed_tasks"] == 1, data
    feedback["id"] = "FB-002"
    feedback["target"] = "order.tasks"
    (feedback_dir / "FB-002.json").write_text(json.dumps(feedback), encoding="utf-8")
    rc, data = run(root, "order.tasks", feature)
    assert data["mode"] == "REFINE" and data["open_feedback"] == ["FB-002"], data

    rc, data = run(root, "order.code", feature)
    assert data["mode"] == "RESUME", data
    rc, data = run(root, "order.plan-check", feature)
    assert data["mode"] == "CHECK", data
    rc, data = run(root, "order.code-to-spec", feature)
    assert data["mode"] == "REFINE", data
    rc, data = run(root, "order.spec", feature, "change behavior")
    assert data["action"] == "EXPLICIT_INPUT" and data["mode"] is None, data

print("All default-mode tests passed")
