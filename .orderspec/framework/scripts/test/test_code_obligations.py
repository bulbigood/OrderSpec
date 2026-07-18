#!/usr/bin/env python3
"""Regression tests for deterministic code-check obligation ledgers."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "code_obligations.py"


def run(root, *args):
    process = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=root,
        env={**os.environ, "ORDERSPEC_ROOT": str(root)},
        capture_output=True,
        text=True,
    )
    return process.returncode, json.loads(process.stdout)


with tempfile.TemporaryDirectory(prefix="orderspec-code-obligations-") as temp:
    root = Path(temp)
    (root / ".orderspec").mkdir()
    feature = root / ".orderspec" / "features" / "001-demo"
    state = feature / ".state"
    state.mkdir(parents=True)
    (feature / "spec.md").write_text(
        "## Requirements\n- **REQ-001**: System MUST work.\n\n"
        "### Story (Priority: P1)\n- **AC-001**: Given input, return output.\n\n"
        "## Invariants\n- **INV-001**: State remains valid.\n",
        encoding="utf-8",
    )
    (state / "mechanisms.tsv").write_text(
        "spec_id\tcoverage_kind\tmechanism\tprimary_files\ttest_type\n"
        "REQ-001\tdirect\tservice\tsrc/service.py\tunit\n",
        encoding="utf-8",
    )
    ledger = state / "code-obligations.json"
    rc, data = run(root, "write-ledger", "--feature-dir", str(feature), "--output", str(ledger))
    assert rc == 0 and data["count"] == 3, data
    stored = json.loads(ledger.read_text(encoding="utf-8"))
    assert stored["obligation_ids"] == ["REQ-001", "AC-001", "INV-001"]
    assert stored["obligations"][1]["priority"] == "P1"

    result_file = root / "result.json"
    result_file.write_text(json.dumps({
        "obligation": "REQ-001",
        "result": "SATISFIED",
        "evidence": ["src/service.py:run"],
        "implementation_paths": ["src/service.py"],
        "finding": None,
    }), encoding="utf-8")
    rc, data = run(root, "record", "--ledger", str(ledger), "--result-file", str(result_file))
    assert rc == 0 and data["assessed"] == 1 and not data["complete"], data

print("All code-obligations tests passed")
