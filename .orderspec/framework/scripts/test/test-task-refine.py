#!/usr/bin/env python3
"""Regression tests for transactional tasks Refine protection."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "task_refine.py"


def run(*args: str) -> tuple[int, dict]:
    result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout)


def tasks_text(completed_gloss: str = "completed behavior", pending_gloss: str = "pending behavior") -> str:
    return f"""# Tasks

**Format (STRICT — pipe-delimited)**

## Task Context (Machine-Readable)

```task-context
{{"version": 1, "tasks": {{"T001": {{"read": ["src/a.py"], "target_state": "mod"}}, "T002": {{"read": ["src/b.py"], "target_state": "mod"}}}}}}
```

---

## Phase 1

- [X] T001 | src/a.py | REQ-001 | {completed_gloss}
- [ ] T002 | src/b.py | REQ-002 | {pending_gloss}
"""


with tempfile.TemporaryDirectory(prefix="orderspec-task-refine-") as temp:
    root = Path(temp)
    tasks = root / "tasks.md"
    snapshot = root / "snapshot.json"
    tasks.write_text(tasks_text(), encoding="utf-8")
    rc, data = run("begin", "--tasks", str(tasks), "--snapshot", str(snapshot))
    assert rc == 0 and data["protected_completed"] == ["T001"]

    tasks.write_text(tasks_text(pending_gloss="refined pending behavior"), encoding="utf-8")
    rc, data = run("validate", "--tasks", str(tasks), "--snapshot", str(snapshot))
    assert rc == 0 and data["ok"] is True

    rc, _ = run("begin", "--tasks", str(tasks), "--snapshot", str(snapshot))
    assert rc == 0
    original = tasks.read_text(encoding="utf-8")
    tasks.write_text(tasks_text(completed_gloss="illegally changed"), encoding="utf-8")
    rc, data = run("validate", "--tasks", str(tasks), "--snapshot", str(snapshot))
    assert rc == 1 and data["restored"] is True
    assert tasks.read_text(encoding="utf-8") == original

print("All task-refine tests passed")
