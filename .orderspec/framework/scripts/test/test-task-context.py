#!/usr/bin/env python3
"""Regression tests for task_context.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "task_context.py"


def run(root: Path, *args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=root,
        env={**os.environ, "ORDERSPEC_ROOT": str(root)},
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid JSON: {result.stdout!r}; stderr={result.stderr!r}") from exc
    return result.returncode, payload


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def write_tasks(feature: Path, block: str, lines: str) -> Path:
    tasks = feature / "tasks.md"
    tasks.write_text(
        "# Tasks\n\n"
        "**Format (STRICT — pipe-delimited, machine-parsed)**\n\n"
        "## Task Context (Machine-Readable)\n\n"
        "```task-context\n"
        f"{block}\n"
        "```\n\n"
        "---\n\n"
        "## Execution Order\n\n"
        f"{lines}\n",
        encoding="utf-8",
    )
    return tasks


def write_plan(feature: Path, entries: str) -> None:
    (feature / "plan.md").write_text(
        f"## Physical Project Structure\n\n```pathmanifest\n{entries}\n```\n",
        encoding="utf-8",
    )


with tempfile.TemporaryDirectory(prefix="orderspec-task-context-") as temp:
    root = Path(temp)
    (root / ".orderspec").mkdir()
    feature = root / ".orderspec" / "features" / "001-demo"
    feature.mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "input.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "src" / "existing.py").write_text("VALUE = 2\n", encoding="utf-8")
    write_plan(feature, "src/existing.py [MOD]\nsrc/new.py [NEW]")

    block = json.dumps(
        {
            "version": 1,
            "tasks": {
                "T001": {"read": ["src/input.py", "src/existing.py"], "target_state": "mod"},
                "T002": {"read": ["src/input.py"], "target_state": "new"},
            },
        },
        indent=2,
    )
    write_tasks(
        feature,
        block,
        "- [ ] T001 | src/existing.py |  | update existing implementation\n"
        "- [ ] T002 | src/new.py |  | create new implementation",
    )

    rc, data = run(root, "validate", "--feature-dir", str(feature))
    expect(rc == 0 and data["total"] == 2, "validate accepts complete task context")

    context_with_refs = json.loads(block)
    context_with_refs["tasks"]["T002"]["contract_refs"] = ["REQ-001", "IF-002"]
    write_tasks(
        feature,
        json.dumps(context_with_refs),
        "- [ ] T001 | src/existing.py |  | update existing implementation\n"
        "- [ ] T002 | src/new.py |  | create new implementation",
    )
    rc, _ = run(root, "validate", "--feature-dir", str(feature))
    expect(rc == 0, "validate accepts optional canonical contract_refs")

    context_with_refs["tasks"]["T002"]["contract_refs"] = ["REQ-1"]
    write_tasks(
        feature,
        json.dumps(context_with_refs),
        "- [ ] T001 | src/existing.py |  | update existing implementation\n"
        "- [ ] T002 | src/new.py |  | create new implementation",
    )
    rc, data = run(root, "validate", "--feature-dir", str(feature))
    expect(
        rc != 0 and any("contract_refs" in error for error in data["validation_errors"]),
        "validate rejects malformed contract_refs",
    )
    write_tasks(
        feature,
        block,
        "- [ ] T001 | src/existing.py |  | update existing implementation\n"
        "- [ ] T002 | src/new.py |  | create new implementation",
    )

    canonical_tasks = (feature / "tasks.md").read_text(encoding="utf-8")
    moved_heading = canonical_tasks.replace(
        "## Task Context (Machine-Readable)", "## Moved Task Context", 1
    ) + "\n## Task Context (Machine-Readable)\n"
    (feature / "tasks.md").write_text(moved_heading, encoding="utf-8")
    rc, data = run(root, "validate", "--feature-dir", str(feature))
    expect(
        rc != 0 and any("before the first horizontal rule" in error for error in data["validation_errors"]),
        "moved task-context heading is rejected",
    )
    (feature / "tasks.md").write_text(canonical_tasks, encoding="utf-8")

    rc, data = run(root, "resolve", "--feature-dir", str(feature), "--task-id", "T001")
    expect(rc == 0, "resolve accepts valid task")
    expect(data["write_paths"] == ["src/existing.py"], "resolve returns exact task write path")
    expect(
        [item["path"] for item in data["to_read"]] == ["src/input.py", "src/existing.py"],
        "resolve preserves declared read order",
    )

    write_tasks(
        feature,
        json.dumps({"version": 1, "tasks": {"T001": {"read": ["src/input.py"], "target_state": "mod"}}}),
        "- [ ] T001 | src/existing.py |  | update existing implementation",
    )
    rc, data = run(root, "validate", "--feature-dir", str(feature))
    expect(rc != 0 and data["error"] == "invalid_task_context", "existing target must be whitelisted")

    write_tasks(
        feature,
        json.dumps({"version": 1, "tasks": {"T001": {"read": ["src/missing.py"], "target_state": "new"}}}),
        "- [ ] T001 | src/new.py |  | create new implementation",
    )
    rc, data = run(root, "resolve", "--feature-dir", str(feature), "--task-id", "T001")
    expect(rc != 0 and "src/missing.py" in data["missing_required"], "missing read file blocks resolution")

    write_tasks(
        feature,
        json.dumps({"version": 1, "tasks": {"T001": {"read": ["src/input.py"], "target_state": "new"}}}),
        "- [ ] T001 | src/new.py |  | create new implementation",
    )
    rc, _ = run(root, "resolve", "--feature-dir", str(feature), "--task-id", "T999")
    expect(rc != 0, "unknown task cannot be resolved")

    write_tasks(
        feature,
        json.dumps({"version": 1, "tasks": {"T001": {"read": ["notes.md"], "target_state": "new"}}}),
        "- [ ] T001 | src/new.py |  | create new implementation",
    )
    (root / "notes.md").write_text("do not pass\n", encoding="utf-8")
    rc, data = run(root, "validate", "--feature-dir", str(feature))
    expect(rc != 0 and "Markdown" in " ".join(data["validation_errors"]), "non-target Markdown read is rejected")

    repeated_new = {
        "version": 1,
        "tasks": {
            "T001": {"read": ["src/input.py"], "target_state": "new"},
            "T002": {"read": ["src/future.py"], "target_state": "new"},
        },
    }
    write_plan(feature, "src/future.py [NEW]")
    write_tasks(
        feature,
        json.dumps(repeated_new),
        "- [ ] T001 | src/future.py |  | create implementation\n"
        "- [ ] T002 | src/future.py |  | extend implementation",
    )
    rc, _ = run(root, "validate", "--feature-dir", str(feature))
    expect(rc == 0, "later task may whitelist a not-yet-created new target")

    write_plan(feature, "src/future.py [NEW]\nsrc/other.py [MOD]")
    write_tasks(
        feature,
        json.dumps(
            {
                "version": 1,
                "tasks": {
                    "T001": {"read": ["src/input.py"], "target_state": "new"},
                    "T002": {"read": ["src/missing.py", "src/other.py"], "target_state": "mod"},
                },
            }
        ),
        "- [ ] T001 | src/future.py |  | create implementation\n"
        "- [ ] T002 | src/other.py |  | consume earlier implementation",
    )
    (root / "src" / "other.py").write_text("VALUE = 4\n", encoding="utf-8")
    rc, _ = run(root, "validate", "--feature-dir", str(feature))
    expect(rc != 0, "unrelated missing path still fails validation")

    write_tasks(
        feature,
        json.dumps(
            {
                "version": 1,
                "tasks": {
                    "T001": {"read": ["src/input.py"], "target_state": "new"},
                    "T002": {"read": ["src/future.py", "src/other.py"], "target_state": "mod"},
                },
            }
        ),
        "- [ ] T001 | src/future.py |  | create implementation\n"
        "- [ ] T002 | src/other.py |  | consume earlier implementation",
    )
    rc, _ = run(root, "validate", "--feature-dir", str(feature))
    expect(rc == 0, "later task may read an earlier new dependency before creation")
    (root / "src" / "future.py").write_text("VALUE = 3\n", encoding="utf-8")
    rc, _ = run(root, "validate", "--feature-dir", str(feature))
    expect(rc == 0, "later task may read an earlier new dependency")

    write_plan(feature, "src/deleted.py [DEL]")
    write_tasks(
        feature,
        json.dumps(
            {
                "version": 1,
                "tasks": {"T001": {"read": ["src/deleted.py"], "target_state": "del"}},
            }
        ),
        "- [X] T001 | src/deleted.py |  | delete obsolete file",
    )
    rc, _ = run(root, "validate", "--feature-dir", str(feature))
    expect(rc == 0, "completed deletion may have a missing target on resume")

print("All task-context tests passed")
