import logging
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TESTS_DIR = Path(__file__).resolve().parent


def run() -> None:
    logging.disable(logging.CRITICAL)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py", top_level_dir=str(ROOT))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

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

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run()

