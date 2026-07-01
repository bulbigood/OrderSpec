#!/usr/bin/env python3
"""run_all_tests.py — master test runner for OrderSpec scripts.

Recursively discovers and runs all test files in .orderspec/framework/scripts/test/.
Aggregates results and exits non-zero if any test failed.
"""

import subprocess
import sys
import time
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
TEST_DIR = SCRIPTS_DIR / "test"

# Discover test files: test-*.py, test_*.py, *_test.py
PATTERNS = ["test-*.py", "test_*.py", "*_test.py"]


def find_test_files() -> list[Path]:
    if not TEST_DIR.exists():
        return []

    files: list[Path] = []
    for pattern in PATTERNS:
        files.extend(sorted(TEST_DIR.rglob(pattern)))

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    return unique


def run_one(test_file: Path) -> tuple[bool, float, str]:
    """Run a single test file. Returns (passed, elapsed_seconds, label)."""
    label = str(test_file.relative_to(SCRIPTS_DIR))
    start = time.time()

    try:
        proc = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.time() - start

        if proc.returncode == 0:
            return True, elapsed, label
        else:
            # Print captured output so user sees what failed
            print(f"\n--- FAIL: {label} (exit {proc.returncode}) ---", flush=True)
            if proc.stdout:
                print(proc.stdout, flush=True)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr, flush=True)
            return False, elapsed, label

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"\n--- TIMEOUT: {label} (120s) ---", flush=True)
        return False, elapsed, label
    except Exception as exc:
        elapsed = time.time() - start
        print(f"\n--- ERROR: {label}: {exc} ---", flush=True)
        return False, elapsed, label


def main() -> int:
    test_files = find_test_files()

    if not test_files:
        print(f"No test files found in {TEST_DIR}", file=sys.stderr)
        print(f"Searched patterns: {PATTERNS}", file=sys.stderr)
        return 1

    print(f"OrderSpec Master Test Runner", flush=True)
    print(f"Found {len(test_files)} test file(s) in {TEST_DIR}", flush=True)
    print(f"{'=' * 60}", flush=True)

    passed = 0
    failed = 0
    total_elapsed = 0.0
    failures: list[str] = []

    for i, tf in enumerate(test_files, start=1):
        label = str(tf.relative_to(SCRIPTS_DIR))
        print(f"[{i}/{len(test_files)}] {label} ... ", end="", flush=True)

        ok, elapsed, _ = run_one(tf)
        total_elapsed += elapsed

        if ok:
            print(f"PASS ({elapsed:.2f}s)", flush=True)
            passed += 1
        else:
            print(f"FAIL ({elapsed:.2f}s)", flush=True)
            failed += 1
            failures.append(label)

    print(f"{'=' * 60}", flush=True)
    print(f"Total: {passed} passed, {failed} failed, {len(test_files)} total", flush=True)
    print(f"Time: {total_elapsed:.2f}s", flush=True)

    if failures:
        print(f"\nFailed tests:", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
