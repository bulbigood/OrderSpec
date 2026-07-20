#!/usr/bin/env python3
"""run_all_tests.py — master test runner for OrderSpec scripts.

Recursively discovers and runs all test files in .orderspec/framework/scripts/test/.
Aggregates results and exits non-zero if any test failed.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
TEST_DIR = SCRIPTS_DIR / "test"

# Canonical discovery pattern for OrderSpec regression tests.
PATTERNS = ["test_*.py"]
TEST_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class TestResult:
    passed: bool
    elapsed: float
    label: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


def default_worker_count() -> int:
    """Leave one hardware thread free, but always allow at least one worker."""
    return max(1, (os.cpu_count() or 1) - 1)


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-j",
        "--workers",
        type=positive_int,
        default=default_worker_count(),
        help="number of parallel test processes (default: CPU threads minus 1)",
    )
    return parser.parse_args(argv)


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


def run_one(test_file: Path) -> TestResult:
    """Run one test process with a private temporary directory."""
    label = str(test_file.relative_to(SCRIPTS_DIR))
    start = time.monotonic()

    try:
        with tempfile.TemporaryDirectory(prefix="orderspec-test-run-") as temp_dir:
            env = os.environ.copy()
            # tempfile-based fixtures in different test processes must never share
            # paths, even when the host has non-standard TMPDIR configuration.
            env.update({"TMPDIR": temp_dir, "TEMP": temp_dir, "TMP": temp_dir})
            proc = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
                env=env,
            )
        elapsed = time.monotonic() - start
        return TestResult(
            passed=proc.returncode == 0,
            elapsed=elapsed,
            label=label,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - start
        return TestResult(
            passed=False,
            elapsed=elapsed,
            label=label,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            error=f"timeout after {TEST_TIMEOUT_SECONDS}s",
        )
    except Exception as exc:
        elapsed = time.monotonic() - start
        return TestResult(False, elapsed, label, error=str(exc))


def print_failure(result: TestResult) -> None:
    if result.error:
        heading = f"ERROR: {result.label}: {result.error}"
    else:
        heading = f"FAIL: {result.label} (exit {result.returncode})"
    print(f"\n--- {heading} ---", flush=True)
    if result.stdout:
        print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    test_files = find_test_files()

    if not test_files:
        print(f"No test files found in {TEST_DIR}", file=sys.stderr)
        print(f"Searched patterns: {PATTERNS}", file=sys.stderr)
        return 1

    print(f"OrderSpec Master Test Runner", flush=True)
    print(f"Found {len(test_files)} test file(s) in {TEST_DIR}", flush=True)
    worker_count = min(args.workers, len(test_files))
    print(f"Workers: {worker_count}", flush=True)
    print(f"{'=' * 60}", flush=True)

    passed = 0
    failed = 0
    failures: list[str] = []
    suite_start = time.monotonic()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(run_one, test_file): test_file for test_file in test_files}
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            status = "PASS" if result.passed else "FAIL"
            print(
                f"[{completed}/{len(test_files)}] {result.label} ... "
                f"{status} ({result.elapsed:.2f}s)",
                flush=True,
            )

            if result.passed:
                passed += 1
            else:
                failed += 1
                failures.append(result.label)
                print_failure(result)

    total_elapsed = time.monotonic() - suite_start

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
