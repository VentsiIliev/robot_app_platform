"""
Example usage of the deprecated two-stage interpolation pipeline.

Demonstrates the deprecated two-stage interpolation pipeline (linear densification -> spline smoothing)
on different geometric shapes. Run directly to generate debug plots for each shape.

Usage:
    python src/engine/robot/path_interpolation/deprecated/points_interpolation_example.py [shape]

Shapes: rectangle, circle, triangle, l_shape, star, all (default: all)
"""

import math
import numpy as np
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))
from src.engine.robot.path_interpolation.deprecated import combined_interpolation
from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import plot_trajectory_debug

# ---------------------------------------------------------------------------
# Shape generators – each returns a list of [x, y, z, rx_degrees, ry_degrees, rz_degrees] points
# that simulate a robot tool-path at a constant Z height.
# ---------------------------------------------------------------------------

Z_HEIGHT = -150.0       # constant working height (mm)
ORIENTATION = [0.0, 0.0, 0.0]  # rx_degrees, ry_degrees, rz_degrees (constant orientation)


def _pt(x, y, z=Z_HEIGHT):
    """Helper: build a 6-DOF point."""
    return [x, y, z] + ORIENTATION


def make_rectangle(width=200, height=100, origin=(0, 0)):
    """Closed rectangular path – 5 points (4 corners + close)."""
    ox, oy = origin
    return [
        _pt(ox,         oy),
        _pt(ox + width, oy),
        _pt(ox + width, oy + height),
        _pt(ox,         oy + height),
        _pt(ox,         oy),  # close the loop
    ]


def make_circle(radius=80, n_points=12, center=(0, 0)):
    """Closed circular path sampled at *n_points* vertices."""
    cx, cy = center
    pts = []
    for i in range(n_points + 1):  # +1 to close
        angle = 2 * math.pi * (i % n_points) / n_points
        pts.append(_pt(cx + radius * math.cos(angle),
                       cy + radius * math.sin(angle)))
    return pts


def make_triangle(side=150, origin=(0, 0)):
    """Equilateral triangle – 4 points (3 vertices + close)."""
    ox, oy = origin
    h = side * math.sqrt(3) / 2
    return [
        _pt(ox,          oy),
        _pt(ox + side,   oy),
        _pt(ox + side/2, oy + h),
        _pt(ox,          oy),  # close
    ]


def make_l_shape(long=200, short=100, width=40, origin=(0, 0)):
    """L-shaped path (open) with a right-angle corner."""
    ox, oy = origin
    return [
        _pt(ox,         oy),
        _pt(ox,         oy + long),
        _pt(ox + width, oy + long),
        _pt(ox + width, oy + short),
        _pt(ox + width + short, oy + short),
        _pt(ox + width + short, oy),
        _pt(ox,         oy),  # close
    ]


def make_star(outer_r=100, inner_r=45, n_tips=5, center=(0, 0)):
    """Star shape with alternating outer/inner vertices."""
    cx, cy = center
    pts = []
    for i in range(2 * n_tips + 1):  # +1 to close
        idx = i % (2 * n_tips)
        angle = math.pi / 2 + 2 * math.pi * idx / (2 * n_tips)
        r = outer_r if idx % 2 == 0 else inner_r
        pts.append(_pt(cx + r * math.cos(angle),
                       cy + r * math.sin(angle)))
    return pts


# ---------------------------------------------------------------------------
# Registry of available shapes
# ---------------------------------------------------------------------------

SHAPES = {
    "rectangle": {
        "fn": make_rectangle,
        "desc": "200x100 mm closed rectangle",
    },
    "circle": {
        "fn": make_circle,
        "desc": "R=80 mm circle (12 vertices)",
    },
    "triangle": {
        "fn": make_triangle,
        "desc": "Equilateral triangle (side=150 mm)",
    },
    "l_shape": {
        "fn": make_l_shape,
        "desc": "L-shaped path with right-angle corner",
    },
    "star": {
        "fn": make_star,
        "desc": "5-pointed star (outer=100, inner=45 mm)",
    },
}


# ---------------------------------------------------------------------------
# Run interpolation in a single shape and plot
# ---------------------------------------------------------------------------

def run_example(shape_name, adaptive_spacing_mm=2.0, smoothing_lambda=10.0):
    """Interpolate a shape and save a debug plot."""
    entry = SHAPES[shape_name]
    path = entry["fn"]()

    print(f"\n{'='*60}")
    print(f"Shape: {shape_name} – {entry['desc']}")
    print(f"Original points: {len(path)}")
    print(f"Adaptive spacing: {adaptive_spacing_mm} mm")
    print(f"Smoothing lambda: {smoothing_lambda}")
    print(f"{'='*60}")

    linear, smoothed = combined_interpolation.interpolate_path_two_stage(
        path,
        adaptive_spacing_mm=adaptive_spacing_mm,
        spline_density_multiplier=2.0,
        smoothing_lambda=smoothing_lambda,
    )

    # Plot original → linear → spline
    plot_trajectory_debug(
        raw_paths=[path],
        curve_paths=[linear],
        sampled_paths=[smoothed],
        save_dir=f"debug_plots/{shape_name}",
    )

    return linear, smoothed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    choice = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    if choice == "all":
        names = list(SHAPES.keys())
    elif choice in SHAPES:
        names = [choice]
    else:
        print(f"Unknown shape '{choice}'. Available: {', '.join(SHAPES.keys())}, all")
        sys.exit(1)

    for name in names:
        run_example(name)

    print("\nDone. Check debug_plots/ for output images.")


if __name__ == "__main__":
    main()
