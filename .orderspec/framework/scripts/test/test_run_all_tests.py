#!/usr/bin/env python3
"""Regression tests for the parallel master test runner."""

import importlib.util
import io
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


RUNNER_PATH = Path(__file__).resolve().parents[1] / "run_all_tests.py"
SPEC = importlib.util.spec_from_file_location("orderspec_run_all_tests", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunAllTestsTest(unittest.TestCase):
    def test_default_worker_count_leaves_one_cpu_free(self) -> None:
        with mock.patch.object(runner.os, "cpu_count", return_value=8):
            self.assertEqual(runner.default_worker_count(), 7)
        with mock.patch.object(runner.os, "cpu_count", return_value=1):
            self.assertEqual(runner.default_worker_count(), 1)
        with mock.patch.object(runner.os, "cpu_count", return_value=None):
            self.assertEqual(runner.default_worker_count(), 1)

    def test_main_runs_tests_concurrently(self) -> None:
        test_files = [runner.SCRIPTS_DIR / "test" / f"fake_{index}.py" for index in range(4)]
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fake_run(test_file: Path) -> runner.TestResult:
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return runner.TestResult(True, 0.05, str(test_file.relative_to(runner.SCRIPTS_DIR)))

        with (
            mock.patch.object(runner, "find_test_files", return_value=test_files),
            mock.patch.object(runner, "run_one", side_effect=fake_run),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(runner.main(["--workers", "2"]), 0)

        self.assertEqual(max_active, 2)

    def test_each_process_gets_a_private_temp_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orderspec-runner-test-") as temp:
            root = Path(temp)
            test_file = root / "temp_isolation.py"
            test_file.write_text(
                "import os, time\n"
                "from pathlib import Path\n"
                "marker = Path(os.environ['TMPDIR']) / 'exclusive'\n"
                "marker.open('x').close()\n"
                "time.sleep(0.05)\n"
                "print(os.environ['TMPDIR'])\n",
                encoding="utf-8",
            )

            with mock.patch.object(runner, "SCRIPTS_DIR", root):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(runner.run_one, [test_file, test_file]))

            self.assertTrue(all(result.passed for result in results), results)
            temp_dirs = [result.stdout.strip() for result in results]
            self.assertEqual(len(set(temp_dirs)), 2)
            self.assertTrue(all(not os.path.exists(path) for path in temp_dirs))


if __name__ == "__main__":
    unittest.main()
