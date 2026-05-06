import io
import logging
import os
import shutil
import sys
import unittest
from pathlib import Path

from coverage import Coverage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TESTS_DIR = Path(__file__).resolve().parent
ARTIFACT_DIRS = [TESTS_DIR / "MagicMock"]


def _clean_test_artifacts() -> None:
    for path in ARTIFACT_DIRS:
        shutil.rmtree(path, ignore_errors=True)


def run() -> None:
    logging.disable(logging.CRITICAL)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _clean_test_artifacts()

    coverage = Coverage(config_file=str(ROOT / ".coveragerc"))
    coverage.start()
    loader = unittest.TestLoader()
    try:
        suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py", top_level_dir=str(ROOT))
    except Exception:
        coverage.stop()
        coverage.save()
        _clean_test_artifacts()
        raise

    stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    runner = unittest.TextTestRunner(verbosity=2, stream=stream)
    try:
        result = runner.run(suite)
    finally:
        coverage.stop()
        coverage.save()
        _clean_test_artifacts()

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failures - errors - skipped

    print("\n" + "=" * 60)
    print(f"  TOTAL   : {total}")
    print(f"  PASSED  : {passed}")
    print(f"  FAILED  : {failures}")
    print(f"  ERRORS  : {errors}")
    print(f"  SKIPPED : {skipped}")
    print("=" * 60)
    coverage.report(show_missing=False, skip_empty=True)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run()
