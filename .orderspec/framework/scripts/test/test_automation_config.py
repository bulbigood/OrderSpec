#!/usr/bin/env python3
"""Regression tests for bootstrap-owned automation configuration management."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


FRAMEWORK = Path(__file__).resolve().parents[2]
SCRIPT = FRAMEWORK / "scripts" / "automation_config.py"
TEMPLATE = FRAMEWORK / "templates" / "automation-config.json"


def run(root: Path, *args: str, stdin: str | None = None):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(root), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )
    return result.returncode, json.loads(result.stdout)


with tempfile.TemporaryDirectory(prefix="orderspec-automation-config-") as temp:
    root = Path(temp)
    (root / ".orderspec" / "framework" / "templates").mkdir(parents=True)
    (root / ".orderspec" / "framework" / "templates" / "automation-config.json").write_text(
        TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    config_path = root / ".orderspec" / "config" / "automation.json"

    rc, result = run(root, "init")
    assert rc == 0 and result["action"] == "created" and result["enabled"] is False, result
    assert config_path.is_file(), config_path
    initial_hash = result["sha256"]

    rc, result = run(root, "init")
    assert rc == 0 and result["action"] == "unchanged" and result["sha256"] == initial_hash, result

    rc, result = run(root, "set-enabled", "--value", "true", "--expected-current-sha256", initial_hash)
    assert rc == 0 and result["action"] == "updated" and result["enabled"] is True, result
    enabled_hash = result["sha256"]

    rc, result = run(root, "set-enabled", "--value", "false", "--expected-current-sha256", initial_hash)
    assert rc == 2 and "changed since inspection" in result["error"], result

    candidate = json.loads(config_path.read_text(encoding="utf-8"))
    candidate["limits"]["max_routes"] = 12
    rc, result = run(
        root, "write", "--input-file", "-", "--expected-current-sha256", enabled_hash,
        stdin=json.dumps(candidate),
    )
    assert rc == 0 and result["action"] == "updated", result
    assert json.loads(config_path.read_text(encoding="utf-8"))["limits"]["max_routes"] == 12

    invalid = {**candidate, "enabled": "yes"}
    before = config_path.read_text(encoding="utf-8")
    rc, result = run(root, "write", "--input-file", "-", stdin=json.dumps(invalid))
    assert rc == 2 and "enabled must be a boolean" in result["error"], result
    assert config_path.read_text(encoding="utf-8") == before

    rc, result = run(root, "validate")
    assert rc == 0 and result["enabled"] is True and result["rule_count"] == 4, result

print("All automation-config tests passed")
