#!/usr/bin/env python3
"""Calculate sequential workpiece-center positions on a rectangular plate.

Coordinates use the plate's local coordinate system with (0, 0) at its
bottom-left corner. Workpieces are placed left-to-right, then bottom-to-top.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
from pathlib import Path


@dataclass(frozen=True)
class PlateLayout:
    width_mm: float
    height_mm: float
    margin_left_mm: float = 0.0
    margin_right_mm: float = 0.0
    margin_bottom_mm: float = 0.0
    margin_top_mm: float = 0.0
    spacing_x_mm: float = 0.0
    spacing_y_mm: float = 0.0
    robot_corners_xy: tuple[tuple[float, float], ...] | None = None

    def __post_init__(self) -> None:
        numeric_values = (
            self.width_mm, self.height_mm,
            self.margin_left_mm, self.margin_right_mm,
            self.margin_bottom_mm, self.margin_top_mm,
            self.spacing_x_mm, self.spacing_y_mm,
        )
        if any(float(value) < 0.0 for value in numeric_values):
            raise ValueError("Plate dimensions, margins, and spacing must be non-negative")
        if self.width_mm <= self.margin_left_mm + self.margin_right_mm:
            raise ValueError("Horizontal margins leave no usable plate width")
        if self.height_mm <= self.margin_bottom_mm + self.margin_top_mm:
            raise ValueError("Vertical margins leave no usable plate height")
        if self.robot_corners_xy is not None and len(self.robot_corners_xy) != 4:
            raise ValueError("Exactly four robot-space plate corners are required")

    @classmethod
    def from_robot_corners(
        cls,
        corners_xy: list[tuple[float, float]] | tuple[tuple[float, float], ...],
        **options: float,
    ) -> "PlateLayout":
        """Build a plate from BL, BR, TR, TL corners measured in robot XY."""
        if len(corners_xy) != 4:
            raise ValueError("Corners must be ordered: bottom-left, bottom-right, top-right, top-left")
        corners = tuple((float(x), float(y)) for x, y in corners_xy)
        bottom_left, bottom_right, top_right, top_left = corners
        width = (_distance(bottom_left, bottom_right) + _distance(top_left, top_right)) / 2.0
        height = (_distance(bottom_left, top_left) + _distance(bottom_right, top_right)) / 2.0
        return cls(width_mm=width, height_mm=height, robot_corners_xy=corners, **options)

    def to_output_xy(self, local_x_mm: float, local_y_mm: float) -> tuple[float, float]:
        """Map plate-local millimetres to robot XY when corners are configured."""
        if self.robot_corners_xy is None:
            return float(local_x_mm), float(local_y_mm)
        u = float(local_x_mm) / float(self.width_mm)
        v = float(local_y_mm) / float(self.height_mm)
        bottom_left, bottom_right, top_right, top_left = self.robot_corners_xy
        return (
            (1.0 - u) * (1.0 - v) * bottom_left[0]
            + u * (1.0 - v) * bottom_right[0]
            + u * v * top_right[0]
            + (1.0 - u) * v * top_left[0],
            (1.0 - u) * (1.0 - v) * bottom_left[1]
            + u * (1.0 - v) * bottom_right[1]
            + u * v * top_right[1]
            + (1.0 - u) * v * top_left[1],
        )


@dataclass(frozen=True)
class Placement:
    width_mm: float
    height_mm: float
    center_x_mm: float
    center_y_mm: float


class PlateWorkpiecePlacer:
    """Stateful shelf-layout placer supporting different workpiece sizes."""

    def __init__(self, layout: PlateLayout) -> None:
        self.layout = layout
        self.reset()

    def reset(self) -> None:
        """Forget prior placements and restart at the bottom-left margin."""
        self._next_left_mm = float(self.layout.margin_left_mm)
        self._row_bottom_mm = float(self.layout.margin_bottom_mm)
        self._row_height_mm = 0.0
        self.placements: list[Placement] = []

    def place_workpiece(
        self,
        workpiece_width_mm: float,
        workpiece_height_mm: float,
    ) -> tuple[float, float] | None:
        """Return the next workpiece center, or ``None`` if it cannot fit.

        A failed placement does not modify the current layout state.
        """
        width = float(workpiece_width_mm)
        height = float(workpiece_height_mm)
        if width <= 0.0 or height <= 0.0:
            raise ValueError("Workpiece width and height must be positive")

        usable_right = float(self.layout.width_mm - self.layout.margin_right_mm)
        usable_top = float(self.layout.height_mm - self.layout.margin_top_mm)
        left = self._next_left_mm
        row_bottom = self._row_bottom_mm
        row_height = self._row_height_mm

        if left + width > usable_right:
            left = float(self.layout.margin_left_mm)
            row_bottom += row_height + float(self.layout.spacing_y_mm)
            row_height = 0.0

        if left + width > usable_right or row_bottom + height > usable_top:
            return None

        center = (left + width / 2.0, row_bottom + height / 2.0)
        self._next_left_mm = left + width + float(self.layout.spacing_x_mm)
        self._row_bottom_mm = row_bottom
        self._row_height_mm = max(row_height, height)
        self.placements.append(Placement(width, height, center[0], center[1]))
        return self.layout.to_output_xy(*center)

    def visualize(self, *, output_path: str | Path | None = None, show: bool = True) -> None:
        """Draw the current layout and optionally save it as an image."""
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon

        figure, axes = plt.subplots(figsize=(10, 7))
        layout = self.layout
        usable_width = layout.width_mm - layout.margin_left_mm - layout.margin_right_mm
        usable_height = layout.height_mm - layout.margin_bottom_mm - layout.margin_top_mm
        plate_points = self._mapped_rectangle(0.0, 0.0, layout.width_mm, layout.height_mm)
        usable_points = self._mapped_rectangle(
            layout.margin_left_mm,
            layout.margin_bottom_mm,
            usable_width,
            usable_height,
        )
        axes.add_patch(Polygon(
            plate_points, closed=True, facecolor="#eeeeee", edgecolor="#222222",
            linewidth=2.0, label="Plate",
        ))
        axes.add_patch(Polygon(
            usable_points, closed=True, facecolor="#ffffff", edgecolor="#777777",
            linewidth=1.5, linestyle="--", label="Usable area",
        ))

        colors = plt.colormaps["tab20"]
        for index, placement in enumerate(self.placements, start=1):
            left = placement.center_x_mm - placement.width_mm / 2.0
            bottom = placement.center_y_mm - placement.height_mm / 2.0
            axes.add_patch(Polygon(
                self._mapped_rectangle(left, bottom, placement.width_mm, placement.height_mm),
                closed=True,
                facecolor=colors((index - 1) % 20),
                edgecolor="#222222",
                linewidth=1.2,
                alpha=0.75,
            ))
            output_center = layout.to_output_xy(placement.center_x_mm, placement.center_y_mm)
            axes.plot(*output_center, "k+", markersize=10)
            axes.text(
                *output_center,
                f"{index}\n({output_center[0]:.1f}, {output_center[1]:.1f})",
                ha="center",
                va="center",
                fontsize=8,
            )

        axes.set_title("Plate workpiece placement")
        coordinate_name = "Robot" if layout.robot_corners_xy is not None else "Plate-local"
        axes.set_xlabel(f"{coordinate_name} X (mm)")
        axes.set_ylabel(f"{coordinate_name} Y (mm)")
        all_x = [point[0] for point in plate_points]
        all_y = [point[1] for point in plate_points]
        x_padding = max(max(all_x) - min(all_x), 1.0) * 0.05
        y_padding = max(max(all_y) - min(all_y), 1.0) * 0.05
        axes.set_xlim(min(all_x) - x_padding, max(all_x) + x_padding)
        axes.set_ylim(min(all_y) - y_padding, max(all_y) + y_padding)
        axes.set_aspect("equal", adjustable="box")
        axes.grid(True, linewidth=0.4, alpha=0.4)
        axes.legend(loc="upper right")
        figure.tight_layout()

        if output_path is not None:
            figure.savefig(Path(output_path), dpi=160, bbox_inches="tight")
        if show:
            plt.show()
        else:
            plt.close(figure)

    def _mapped_rectangle(
        self,
        left_mm: float,
        bottom_mm: float,
        width_mm: float,
        height_mm: float,
    ) -> list[tuple[float, float]]:
        return [
            self.layout.to_output_xy(left_mm, bottom_mm),
            self.layout.to_output_xy(left_mm + width_mm, bottom_mm),
            self.layout.to_output_xy(left_mm + width_mm, bottom_mm + height_mm),
            self.layout.to_output_xy(left_mm, bottom_mm + height_mm),
        ]


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Save the visualization as PNG/PDF/SVG")
    parser.add_argument("--no-show", action="store_true", help="Do not open the plot window")
    parser.add_argument(
        "--robot-space-demo",
        action="store_true",
        help="Use four example robot-space plate corners",
    )
    args = parser.parse_args()

    layout_options = dict(
        margin_left_mm=20.0, margin_right_mm=20.0,
        margin_bottom_mm=15.0, margin_top_mm=15.0,
        spacing_x_mm=10.0, spacing_y_mm=10.0,
    )
    layout = (
        PlateLayout.from_robot_corners(
            # Required order: bottom-left, bottom-right, top-right, top-left.
            [(250.0, 100.0), (740.0, 200.0), (680.0, 495.0), (190.0, 395.0)],
            **layout_options,
        )
        if args.robot_space_demo
        else PlateLayout(width_mm=500.0, height_mm=300.0, **layout_options)
    )
    placer = PlateWorkpiecePlacer(layout)

    workpieces = [
        (100.0, 60.0),
        (120.0, 80.0),
        (100.0, 40.0),
        (90.0, 110.0),
        (180.0, 50.0),
        (75.0, 95.0),
        (130.0, 70.0),
        (60.0, 35.0),
        # This deliberately cannot fit after the preceding placements.
        (300.0, 140.0),
    ]
    for width, height in workpieces:
        center = placer.place_workpiece(width, height)
        if center is None:
            print(f"workpiece={width:g}x{height:g} mm NOT PLACED: no remaining space")
        else:
            print(f"workpiece={width:g}x{height:g} mm center={center}")
    placer.visualize(output_path=args.output, show=not args.no_show)


if __name__ == "__main__":
    main()
