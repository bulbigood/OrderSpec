#!/usr/bin/env python3
"""Integration regression for bounded work-order capture and rollback."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "work_order.py"
ROOT = SCRIPT.parents[3]
FEATURES = ROOT / ".orderspec" / "features"
FEATURES.mkdir(parents=True, exist_ok=True)
feature = Path(tempfile.mkdtemp(prefix="test-work-order-", dir=FEATURES))


def run(*args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=ROOT, capture_output=True, text=True
    )
    return result.returncode, json.loads(result.stdout)


try:
    target = feature / "generated.txt"
    rel_target = target.relative_to(ROOT).as_posix()
    (feature / "plan.md").write_text(
        f"## Physical Project Structure\n\n```pathmanifest\n{rel_target} [NEW]\n```\n",
        encoding="utf-8",
    )
    (feature / "tasks.md").write_text(
        f"# Tasks\n\n## Phase 1\n\n- [ ] T001 | {rel_target} | REQ-001 | generate file\n",
        encoding="utf-8",
    )
    rc, captured = run("capture", "--feature-dir", str(feature))
    assert rc == 0 and captured["paths"] == 1

    target.write_text("implementation\n", encoding="utf-8")
    tasks = feature / "tasks.md"
    tasks.write_text(tasks.read_text(encoding="utf-8").replace("- [ ]", "- [X]"), encoding="utf-8")

    rc, preview = run("rollback", "--feature-dir", str(feature))
    assert rc == 0 and preview["mode"] == "preview" and target.is_file()
    assert preview["actions"][0]["action"] == "delete", preview

    rc, applied = run("rollback", "--feature-dir", str(feature), "--apply")
    assert rc == 0 and applied["checkboxes_reset"] == 1
    assert not target.exists() and "- [ ] T001" in tasks.read_text(encoding="utf-8")
finally:
    target.unlink(missing_ok=True)
    shutil.rmtree(feature, ignore_errors=True)

print("All work-order tests passed")
