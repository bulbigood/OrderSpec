#!/usr/bin/env python3
"""Regression: code halt -> spec refine -> tasks refine -> code resume."""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
MODE = SCRIPTS / "default_mode.py"
TASK_REFINE = SCRIPTS / "task_refine.py"


def json_run(script: Path, *args: str) -> tuple[int, dict]:
    process = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)
    return process.returncode, json.loads(process.stdout)


def tasks_text(t002_ref: str = "REQ-007", t002_gloss: str = "implement pending model") -> str:
    return f"""# Tasks

**Format (STRICT — pipe-delimited)**

## Task Context (Machine-Readable)

```task-context
{{"version": 1, "tasks": {{"T001": {{"read": ["src/a.py"], "target_state": "mod"}}, "T002": {{"read": ["src/b.py"], "target_state": "mod", "contract_refs": ["{t002_ref}"]}}}}}}
```

---

## Phase 1

- [X] T001 | src/a.py | REQ-001 | completed implementation
- [ ] T002 | src/b.py | {t002_ref} | {t002_gloss}
"""


with tempfile.TemporaryDirectory(prefix="orderspec-feedback-recovery-") as temp:
    feature = Path(temp) / ".orderspec" / "features" / "001-demo"
    feedback_dir = feature / ".state" / "feedback"
    feedback_dir.mkdir(parents=True)
    spec = feature / "spec.md"
    plan = feature / "plan.md"
    tasks = feature / "tasks.md"
    spec.write_text("# Spec\n\nREQ-007 existing behavior\n", encoding="utf-8")
    plan.write_text("# Plan\n", encoding="utf-8")
    tasks.write_text(tasks_text(), encoding="utf-8")
    completed_line = "- [X] T001 | src/a.py | REQ-001 | completed implementation"

    feedback = {
        "version": 1,
        "id": "FB-001",
        "status": "open",
        "source": "order.code",
        "target": "order.spec",
        "requested_change": "add stable schema contract IDs",
    }
    (feedback_dir / "FB-001.json").write_text(json.dumps(feedback), encoding="utf-8")

    rc, mode = json_run(MODE, "resolve", "--command", "order.spec", "--feature-dir", str(feature))
    assert rc == 0 and mode["mode"] == "REFINE" and mode["open_feedback"] == ["FB-001"], mode

    time.sleep(0.002)
    spec.write_text("# Spec\n\nREQ-007 existing behavior\nREQ-010 task schema\nREQ-011 audit schema\n", encoding="utf-8")
    feedback["status"] = "consumed"
    (feedback_dir / "FB-001.json").write_text(json.dumps(feedback), encoding="utf-8")

    rc, mode = json_run(MODE, "resolve", "--command", "order.plan", "--feature-dir", str(feature))
    assert rc == 0 and mode["mode"] == "RECONCILE" and mode["classify_impact_before_write"], mode
    # Contract enrichment uses the existing mapping, so plan remains byte-identical.
    original_plan = plan.read_bytes()

    rc, mode = json_run(MODE, "resolve", "--command", "order.tasks", "--feature-dir", str(feature))
    assert rc == 0 and mode["mode"] == "REFINE" and mode["upstream_newer"], mode
    snapshot = feature / ".state" / "tasks-refine-snapshot.json"
    rc, begun = json_run(TASK_REFINE, "begin", "--tasks", str(tasks), "--snapshot", str(snapshot))
    assert rc == 0 and begun["protected_completed"] == ["T001"], begun
    tasks.write_text(tasks_text("REQ-010,REQ-011", "implement model from stable schema contracts"), encoding="utf-8")
    rc, validated = json_run(TASK_REFINE, "validate", "--tasks", str(tasks), "--snapshot", str(snapshot))
    assert rc == 0 and validated["ok"], validated
    assert completed_line in tasks.read_text(encoding="utf-8")
    assert plan.read_bytes() == original_plan

    rc, mode = json_run(MODE, "resolve", "--command", "order.code", "--feature-dir", str(feature))
    assert rc == 0 and mode["mode"] == "RESUME", mode

print("All feedback recovery flow tests passed")
