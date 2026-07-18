"""Shared workspace and CLI harness for frontmatter tests."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
PY = sys.executable
TRACE = SCRIPT_DIR.parent / "traceability.py"

if not TRACE.exists():
    print(f"FATAL: traceability.py not found at {TRACE}", file=sys.stderr)
    sys.exit(2)

WORK = Path(tempfile.mkdtemp(prefix="orderspec-test-fm-"))

pass_count = 0
fail_count = 0


def ok(name):
    global pass_count
    pass_count += 1
    print(f"PASS: {name}", flush=True)


def bad(name, detail=""):
    global fail_count
    fail_count += 1
    msg = f"FAIL: {name}"
    if detail:
        msg += f" :: {detail}"
    print(msg, flush=True)


def run_vfm(artifact_type, file_path, use_json=True):
    """Run validate-frontmatter and return (rc, data_or_text)."""
    cmd = [PY, str(TRACE), "validate-frontmatter"]
    if use_json:
        cmd.append("--json")
    cmd.extend([artifact_type, str(file_path)])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if use_json:
        try:
            return proc.returncode, json.loads(proc.stdout)
        except Exception:
            return proc.returncode, proc.stdout + proc.stderr
    return proc.returncode, proc.stdout + proc.stderr


def write_file(name, content):
    path = WORK / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def finish() -> None:
    """Remove the workspace, print the result summary, and exit."""
    import shutil

    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)

    print(f"\n{pass_count} passed, {fail_count} failed", flush=True)
    raise SystemExit(0 if fail_count == 0 else 1)
