#!/usr/bin/env python3
"""
Compile translation files for the glue dispensing dashboard.

Expected layout:
    translations/
        de/
            glue_de.qts  →  glue_de.qm
        fr/
            glue_fr.qts  →  glue_fr.qm
        ...

Usage:
    python compile.py              # compile all languages
    python compile.py de fr        # compile specific languages only
"""

import sys
import subprocess
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent / "translations"


def find_lrelease() -> str | None:
    for cmd in ("lrelease", "lrelease-qt6", "pyside6-lrelease"):
        try:
            result = subprocess.run([cmd, "-version"], capture_output=True, text=True)
            if result.returncode == 0:
                return cmd
        except FileNotFoundError:
            continue
    return None


def compile_language(lang_dir: Path, lrelease: str) -> bool:
    ts_files = list(lang_dir.glob("*.qts"))
    if not ts_files:
        print(f"  [skip] no .qts files in {lang_dir.name}/")
        return True

    success = True
    for ts_file in ts_files:
        qm_file = ts_file.with_suffix(".qm")
        result = subprocess.run(
            [lrelease, str(ts_file), "-qm", str(qm_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and qm_file.exists():
            print(f"  [ok]   {ts_file.parent.name}/{ts_file.name} → {qm_file.name}")
        else:
            print(f"  [fail] {ts_file.name}: {result.stderr.strip()}")
            success = False

    return success


def main(langs: list[str] | None = None) -> bool:
    lrelease = find_lrelease()
    if not lrelease:
        print("ERROR: lrelease not found.")
        print("  Ubuntu/Debian: sudo apt install qt6-tools-dev")
        print("  pip:           pip install PySide6")
        return False

    print(f"Using: {lrelease}\n")

    if langs:
        lang_dirs = [TRANSLATIONS_DIR / lang for lang in langs]
        missing = [d for d in lang_dirs if not d.is_dir()]
        if missing:
            print(f"ERROR: directory not found: {[str(d) for d in missing]}")
            return False
    else:
        lang_dirs = sorted(d for d in TRANSLATIONS_DIR.iterdir() if d.is_dir())

    if not lang_dirs:
        print(f"No language directories found in {TRANSLATIONS_DIR}")
        return False

    all_ok = True
    for lang_dir in lang_dirs:
        print(f"[{lang_dir.name}]")
        ok = compile_language(lang_dir, lrelease)
        all_ok = all_ok and ok

    print(f"\n{'OK' if all_ok else 'FAILED'} — {len(lang_dirs)} language(s) processed")
    return all_ok


if __name__ == "__main__":
    requested = sys.argv[1:] or None
    sys.exit(0 if main(requested) else 1)