#!/usr/bin/env python3
"""
Run the test suite with coverage and print a report.

Usage:
    python run_coverage.py                  # text report in terminal
    python run_coverage.py --html           # also open htmlcov/index.html
    python run_coverage.py --missing        # show missing line numbers
    python run_coverage.py --fail-under 50  # exit 1 if below 50 %

Requirements:
    pip install coverage
    (or: .venv/bin/pip install coverage)
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tests with coverage")
    parser.add_argument("--html",        action="store_true", help="Generate HTML report and open it")
    parser.add_argument("--missing",     action="store_true", help="Show missing line numbers in terminal report")
    parser.add_argument("--fail-under",  type=int, default=0, metavar="PCT",
                        help="Exit with code 2 if total coverage is below PCT")
    parser.add_argument("--module",      default="src",       metavar="PATH",
                        help="Source path to measure (default: src)")
    args = parser.parse_args()

    python = sys.executable

    # ── 1. Check coverage is installed ────────────────────────────────────────
    result = subprocess.run([python, "-m", "coverage", "--version"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("coverage not found. Install it:")
        print("  pip install coverage")
        print("  # or: .venv/bin/pip install coverage")
        sys.exit(1)

    # ── 2. Run tests under coverage ────────────────────────────────────────────
    print("=" * 60)
    print("Running tests with coverage...")
    print("=" * 60)

    run_cmd = [
        python, "-m", "coverage", "run",
        f"--source={args.module}",
        "--branch",                          # measure branch coverage too
        "--omit=*/__pycache__/*,*/test_*",
        "-m", "unittest", "discover",
        "-s", str(ROOT / "tests"),
        "-p", "test_*.py",
        "--top-level-dir", str(ROOT),
    ]

    run_result = subprocess.run(run_cmd, cwd=str(ROOT))

    # ── 3. Terminal report ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Coverage report")
    print("=" * 60)

    report_cmd = [python, "-m", "coverage", "report", f"--rcfile={ROOT}/.coveragerc"]
    if args.missing:
        report_cmd.append("--show-missing")
    if args.fail_under:
        report_cmd.append(f"--fail-under={args.fail_under}")

    subprocess.run(report_cmd, cwd=str(ROOT))

    # ── 4. HTML report ─────────────────────────────────────────────────────────
    if args.html:
        print("\nGenerating HTML report...")
        subprocess.run([python, "-m", "coverage", "html",
                        "--directory=htmlcov"], cwd=str(ROOT))

        html_index = ROOT / "htmlcov" / "index.html"
        print(f"HTML report written to: {html_index}")

        # Try to open in browser
        import os
        if sys.platform == "linux":
            os.system(f"xdg-open '{html_index}' &")
        elif sys.platform == "darwin":
            os.system(f"open '{html_index}'")
        elif sys.platform.startswith("win"):
            os.startfile(str(html_index))

    sys.exit(run_result.returncode)


if __name__ == "__main__":
    main()
