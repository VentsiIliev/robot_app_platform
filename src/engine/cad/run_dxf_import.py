from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.engine.cad.dxf_workpiece_importer import (
    DxfImportOptions,
    import_dxf_to_workpiece_data,
)

DEFAULT_DXF_PATH = "/home/ilv/Downloads/centered_100x100_square_valid.dxf"
DEFAULT_OUTPUT_PATH = "/home/ilv/Downloads/centered_100x100_square.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a DXF file into platform workpiece data.",
    )
    parser.add_argument(
        "dxf_path",
        nargs="?",
        default=DEFAULT_DXF_PATH,
        help=f"Path to the input .dxf file (default: {DEFAULT_DXF_PATH})",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output path for the generated workpiece JSON",
        default=DEFAULT_OUTPUT_PATH,
    )
    parser.add_argument(
        "--flatten-distance",
        type=float,
        default=0.5,
        help="Flattening tolerance for ARC/CIRCLE/ELLIPSE/SPLINE sampling",
    )
    parser.add_argument(
        "--connect-tolerance",
        type=float,
        default=0.5,
        help="Endpoint tolerance used to stitch paths into loops",
    )
    parser.add_argument(
        "--keep-origin",
        action="store_true",
        help="Keep original DXF coordinates instead of normalizing contour min(x,y) to (0,0)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print the full generated JSON to stdout",
    )
    return parser


def _contour_bounds(contour: list[list[list[float]]]) -> tuple[float, float, float, float]:
    points = [point[0] for point in contour if point and point[0]]
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    dxf_path = Path(args.dxf_path).expanduser().resolve()
    if not dxf_path.exists():
        parser.error(f"DXF file not found: {dxf_path}")

    options = DxfImportOptions(
        flatten_distance=float(args.flatten_distance),
        connect_tolerance=float(args.connect_tolerance),
        normalize_to_origin=not bool(args.keep_origin),
    )

    workpiece = import_dxf_to_workpiece_data(str(dxf_path), options=options)
    contour = workpiece.get("contour") or []
    if not contour:
        parser.error("Importer returned an empty contour")

    min_x, min_y, max_x, max_y = _contour_bounds(contour)
    print(f"DXF: {dxf_path}")
    print(f"Contour points: {len(contour)}")
    print(f"Bounds: min=({min_x:.3f}, {min_y:.3f}) max=({max_x:.3f}, {max_y:.3f})")
    print(f"Normalized to origin: {not bool(args.keep_origin)}")

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(workpiece, handle, indent=2)
        print(f"Saved JSON: {output_path}")

    if args.pretty:
        print(json.dumps(workpiece, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())