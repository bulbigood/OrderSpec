#!/usr/bin/env python3
"""Test setup.py --shell-vars output format."""

import subprocess
import os
from pathlib import Path

# Используем текущую рабочую директорию, так как тест запускается из корня проекта
REPO_ROOT = os.getcwd()

def test_shell_vars_output():
    """Test that --shell-vars produces eval-ready shell assignments."""
    cmd = ["python3", ".orderspec/framework/scripts/setup.py", "paths", "--shell-vars"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT
    )
    
    if result.returncode != 0:
        print(f"REPO_ROOT: {REPO_ROOT}")
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        assert False, f"Expected exit 0, got {result.returncode}"
    
    assert result.stdout, "Expected non-empty stdout"
    
    lines = result.stdout.strip().split("\n")
    required_keys = {"REPO_ROOT", "FEATURE_ID", "FEATURE_DIR", "FEATURE_SPEC", "IMPL_PLAN"}
    found_keys = set()
    
    for line in lines:
        if "=" in line and line.split("=")[0] in required_keys:
            key = line.split("=")[0]
            found_keys.add(key)
            assert '"' in line, f"Expected quoted value: {line}"
    
    assert required_keys.issubset(found_keys), f"Missing keys: {required_keys - found_keys}"

def test_json_still_works():
    """Test that --json still works as default."""
    cmd = ["python3", ".orderspec/framework/scripts/setup.py", "paths", "--json"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT
    )

    if result.returncode != 0:
        print(f"REPO_ROOT: {REPO_ROOT}")
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        assert False, f"Expected exit 0, got {result.returncode}"
    
    assert result.stdout.startswith("{"), "Expected JSON output"

if __name__ == "__main__":
    test_shell_vars_output()
    test_json_still_works()
    print("All tests passed!")
