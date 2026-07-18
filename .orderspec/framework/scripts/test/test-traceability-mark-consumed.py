#!/usr/bin/env python3
"""Test: traceability.py mark-consumed writes correct CONSUMED_STALE marker."""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "traceability.py"

def test_mark_consumed():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Some report content\n\nverdict: BLOCK\n")
        report_path = f.name
    
    try:
        result = subprocess.run(
            [
                "python3", str(SCRIPT), "mark-consumed",
                "--report", report_path,
                "--consumer", "/order.spec",
                "--recheck", "/order.spec-check",
            ],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"FAIL: mark-consumed exited {result.returncode}: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        
        content = Path(report_path).read_text()
        
        if "CONSUMED_STALE" not in content:
            print(f"FAIL: CONSUMED_STALE marker not found in output", file=sys.stderr)
            sys.exit(1)
        
        if "not a PASS verdict" not in content:
            print(f"FAIL: 'not a PASS verdict' not found", file=sys.stderr)
            sys.exit(1)
        
        if "orderspec-report-state: CONSUMED_STALE" not in content:
            print("FAIL: machine-readable consumed marker not found", file=sys.stderr)
            sys.exit(1)

        if "/order.spec" not in content or "/order.spec-check" not in content:
            print("FAIL: consumer/recheck references not found", file=sys.stderr)
            sys.exit(1)
        
        print("OK: mark-consumed writes correct CONSUMED_STALE marker")
    finally:
        Path(report_path).unlink(missing_ok=True)

if __name__ == "__main__":
    test_mark_consumed()
    print("All tests passed")
