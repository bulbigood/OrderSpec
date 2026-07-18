#!/usr/bin/env python3
"""Regression tests for persistent cross-stage feedback."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "workflow_feedback.py"


def run(*args: str, stdin: str | None = None) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True
    )
    return result.returncode, json.loads(result.stdout)


with tempfile.TemporaryDirectory(prefix="orderspec-feedback-") as temp:
    feature = Path(temp) / ".orderspec" / "features" / "FEAT-001-example"
    feature.mkdir(parents=True)
    rc, created = run(
        "create", "--feature-dir", str(feature), "--source", "order.code",
        "--target", "order.tasks", "--category", "task_decomposition",
        "--location", "T003", "--summary", "missing prerequisite",
        "--evidence", "worker requested src/dependency.py",
        "--requested-change", "add prerequisite task before T003",
    )
    assert rc == 0 and created["feedback"]["id"] == "FB-001"
    rc, listed = run("list", "--feature-dir", str(feature), "--target", "order.tasks")
    assert rc == 0 and listed["count"] == 1
    rc, consumed = run(
        "consume", "--feature-dir", str(feature), "--id", "FB-001", "--consumer", "order.tasks"
    )
    assert rc == 0 and consumed["feedback"]["status"] == "consumed"
    rc, listed = run("list", "--feature-dir", str(feature), "--target", "order.tasks")
    assert rc == 0 and listed["count"] == 0

    input_file = feature / "feedback-input.json"
    input_file.write_text(
        json.dumps(
            {
                "source": "order.code",
                "target": "order.plan",
                "category": "plan_mapping",
                "location": "T004",
                "summary": "mapping missing",
                "evidence": "line one\nline two with $ and quotes \"preserved\"",
                "requested_change": "map the missing boundary",
            }
        ),
        encoding="utf-8",
    )
    rc, created = run("create", "--feature-dir", str(feature), "--input-file", str(input_file))
    assert rc == 0 and created["feedback"]["evidence"].startswith("line one\nline two")

    stdin_payload = {
        "source": "order.code",
        "target": "order.spec",
        "category": "contract_context",
        "summary": "schema IDs missing",
        "evidence": "T002 cannot resolve fields",
        "requested_change": "add stable field contract IDs",
    }
    rc, created = run(
        "create", "--feature-dir", str(feature), "--input-file", "-",
        stdin=json.dumps(stdin_payload),
    )
    assert rc == 0 and created["feedback"]["id"] == "FB-003", created

print("All workflow-feedback tests passed")
