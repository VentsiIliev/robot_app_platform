from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.robot_systems.paint.processes.paint.plan.paint_contour_interpolation import (
        PaintContourInterpolationResult,
    )


def save_paint_contour_interpolation_debug_plot(
    result: "PaintContourInterpolationResult",
    output_path: str | Path,
) -> Path:
    """Save a compact before/after plot for the experimental interpolation."""
    import matplotlib.pyplot as plt

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig = _build_debug_figure(result)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def show_paint_contour_interpolation_debug_plot(
    result: "PaintContourInterpolationResult",
) -> None:
    """Show a compact before/after plot for the experimental interpolation."""
    import matplotlib.pyplot as plt

    _build_debug_figure(result)
    plt.show()


def _build_debug_figure(result: "PaintContourInterpolationResult"):
    import matplotlib.pyplot as plt

    from src.robot_systems.paint.processes.paint.plan.paint_contour_interpolation import (
        compute_min_rect_metrics,
    )

    raw = np.asarray(result.raw_path, dtype=float)
    prepared = np.asarray(result.prepared_path, dtype=float)
    execution = np.asarray(result.execution_path, dtype=float)
    anchors = np.asarray(result.anchor_xy, dtype=float).reshape(-1, 2) if result.anchor_xy else np.empty((0, 2))
    cleaned = (
        np.asarray(result.cleaned_anchor_xy, dtype=float).reshape(-1, 2)
        if result.cleaned_anchor_xy else np.empty((0, 2))
    )
    boundaries = (
        np.asarray(result.sharp_boundary_xy, dtype=float).reshape(-1, 2)
        if result.sharp_boundary_xy else np.empty((0, 2))
    )

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    raw_rect = compute_min_rect_metrics(raw[:, :2] if len(raw) else np.empty((0, 2)))
    execution_rect = compute_min_rect_metrics(execution[:, :2] if len(execution) else np.empty((0, 2)))
    units = result.units
    fig.suptitle(
        "Paint Contour Interpolation Experiment: "
        f"raw={len(raw)} cleaned={len(cleaned)} prepared={len(prepared)} execution={len(execution)} | "
        f"rect raw={raw_rect['width_mm']:.2f}x{raw_rect['height_mm']:.2f}{units} "
        f"final={execution_rect['width_mm']:.2f}x{execution_rect['height_mm']:.2f}{units} "
        f"delta={execution_rect['width_mm'] - raw_rect['width_mm']:+.2f}x"
        f"{execution_rect['height_mm'] - raw_rect['height_mm']:+.2f}{units}",
        fontsize=12,
    )
    _plot_xy(axes[0], raw, "Raw", units)
    _plot_xy(axes[1], prepared, "Anchor-Preserving Support", units)
    _plot_xy(axes[2], execution, "Final Execution", units)
    _plot_min_rect(axes[0], raw_rect, "raw rect")
    _plot_min_rect(axes[2], execution_rect, "final rect")
    for axis in axes:
        if len(anchors):
            axis.scatter(anchors[:, 0], anchors[:, 1], s=20, c="orange", label="anchors", zorder=4)
        if len(cleaned):
            axis.scatter(cleaned[:, 0], cleaned[:, 1], s=12, c="tab:blue", label="cleaned", zorder=4)
        if len(boundaries):
            axis.scatter(boundaries[:, 0], boundaries[:, 1], s=45, c="cyan", edgecolors="black", label="sharp", zorder=5)
        axis.set_aspect("equal", adjustable="box")
        axis.grid(True, alpha=0.5)
        axis.legend(loc="best")
    fig.tight_layout()
    return fig


def _plot_min_rect(axis, rect: dict[str, float], label: str) -> None:
    import cv2

    if rect["width_mm"] <= 1e-9 or rect["height_mm"] <= 1e-9:
        return
    cv_rect = (
        (float(rect["cx_mm"]), float(rect["cy_mm"])),
        (float(rect["width_mm"]), float(rect["height_mm"])),
        float(rect["angle_deg"]),
    )
    box = cv2.boxPoints(cv_rect)
    box = np.vstack([box, box[:1]])
    axis.plot(box[:, 0], box[:, 1], "--", linewidth=1.5, label=label)


def _plot_xy(axis, path: np.ndarray, title: str, units: str) -> None:
    axis.set_title(f"{title} ({len(path)} pts)")
    if len(path) == 0:
        return
    axis.plot(path[:, 0], path[:, 1], "-o", markersize=2)
    axis.scatter([path[0, 0]], [path[0, 1]], s=45, c="green", label="start", zorder=6)
    axis.scatter([path[-1, 0]], [path[-1, 1]], s=45, c="red", label="end", zorder=6)
    axis.set_xlabel(f"X ({units})")
    axis.set_ylabel(f"Y ({units})")
