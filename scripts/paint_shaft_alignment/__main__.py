from __future__ import annotations

if __package__ in (None, ""):
    import os
    import sys

    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from scripts.paint_shaft_alignment.cli import main
else:
    from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
