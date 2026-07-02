#!/usr/bin/env python3
"""Regression test: traceability.py get must work with --feature-dir without positional <feature>."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "traceability.py"

def run_cmd(args, cwd=None):
    result = subprocess.run(
        ["python3", str(SCRIPT)] + args,
        capture_output=True, text=True, cwd=cwd
    )
    return result.returncode, result.stdout, result.stderr

def test_get_spec_ids_with_feature_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        feature_dir = tmpdir / ".orderspec" / "features" / "test-feature"
        state_dir = feature_dir / ".state"
        state_dir.mkdir(parents=True)
        
        specids = state_dir / "spec-ids.tsv"
        specids.write_text(
            "#orderspec spec-ids v1\n"
            "spec_id\tkind\tsection\n"
            "REQ-001\tREQ\tfunctional\n"
        )
        (state_dir / ".schema").write_text("v1\n")
        
        rc, out, err = run_cmd([
            "-C", str(tmpdir),
            "--feature-dir", str(feature_dir),
            "get", "spec-ids"
        ])
        
        if rc != 0:
            print(f"FAIL: get with --feature-dir failed: {err}", file=sys.stderr)
            sys.exit(1)
        
        if "REQ-001" not in out:
            print(f"FAIL: expected REQ-001 in output, got: {out}", file=sys.stderr)
            sys.exit(1)
        
        print("OK: get spec-ids works with --feature-dir and single positional arg")

if __name__ == "__main__":
    test_get_spec_ids_with_feature_dir()
    print("All tests passed")
