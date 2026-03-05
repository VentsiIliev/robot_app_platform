import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

import numpy as np

_DEBUG_DIR = Path(__file__).resolve().parent / "output"


def _ensure_debug_dir() -> Path:
    _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    return _DEBUG_DIR


def _to_2d(contour) -> np.ndarray:
    pts = np.asarray(contour, dtype=np.float32)
    if pts.ndim == 3:
        pts = pts[:, 0, :]
    return pts.reshape(-1, 2)


def _create_debug_plot(contour1, contour2, metrics: dict) -> None:
    import matplotlib.pyplot as plt

    debug_dir = _ensure_debug_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    points1 = _to_2d(contour1)
    points2 = _to_2d(contour2)

    np.save(debug_dir / f"contour1_{timestamp}.npy", points1)
    np.save(debug_dir / f"contour2_{timestamp}.npy", points2)

    similarity_percent = metrics.get("similarity_percent", 0)
    area_diff          = metrics.get("area_diff", None)
    area_ratio         = metrics.get("area_ratio", None)
    moment_diff        = metrics.get("moment_diff", None)

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))

    ax1.plot(points1[:, 0], points1[:, 1], "b-", linewidth=2, marker="o", markersize=3)
    ax1.set_title("Contour 1 (Reference)")
    ax1.set_aspect("equal")
    ax1.grid(True, alpha=0.3)
    ax1.invert_yaxis()

    ax2.plot(points2[:, 0], points2[:, 1], "r-", linewidth=2, marker="s", markersize=3)
    ax2.set_title("Contour 2 (Test)")
    ax2.set_aspect("equal")
    ax2.grid(True, alpha=0.3)
    ax2.invert_yaxis()

    ax3.plot(points1[:, 0], points1[:, 1], "b-", linewidth=2, label="Contour 1", alpha=0.7)
    ax3.plot(points2[:, 0], points2[:, 1], "r-", linewidth=2, label="Contour 2", alpha=0.7)
    ax3.set_title(f"Overlay — Similarity: {similarity_percent:.2f}%")
    ax3.set_aspect("equal")
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    ax3.invert_yaxis()

    metrics_text = (
        f"moment_diff : {moment_diff:.4f}\n" if moment_diff is not None else "moment_diff : N/A\n"
    ) + (
        f"area_diff   : {area_diff:.2f}\n" if area_diff is not None else "area_diff   : N/A\n"
    ) + (
        f"area_ratio  : {area_ratio:.4f}\n" if area_ratio is not None else "area_ratio  : N/A\n"
    ) + f"similarity  : {similarity_percent:.2f}%"

    fig.text(0.01, 0.01, metrics_text, fontsize=8, verticalalignment="bottom",
             bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    out_path = debug_dir / f"similarity_debug_{timestamp}_{similarity_percent:.1f}pct.png"
    plt.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"🔍 Similarity debug plot saved: {out_path}")


def get_similarity_debug_plot(
    workpiece_contour,
    contour,
    workpiece_centroid: Tuple,
    contour_centroid: Tuple,
    wp_angle: float,
    contour_angle: float,
    centroid_diff: np.ndarray,
    rotation_diff: float,
) -> None:
    import matplotlib.pyplot as plt

    debug_dir = _ensure_debug_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    pts_wp = _to_2d(workpiece_contour.get() if hasattr(workpiece_contour, "get") else workpiece_contour)
    pts_c  = _to_2d(contour.get() if hasattr(contour, "get") else contour)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.plot(pts_wp[:, 0], pts_wp[:, 1], "b-", linewidth=2, label="Workpiece")
    ax1.plot(pts_c[:, 0],  pts_c[:, 1],  "r-", linewidth=2, label="Detected")
    ax1.plot(*workpiece_centroid, "b+", markersize=12)
    ax1.plot(*contour_centroid,   "r+", markersize=12)
    ax1.set_title("Contours overlay")
    ax1.set_aspect("equal")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.invert_yaxis()

    info = (
        f"WP angle       : {wp_angle:.2f}°\n"
        f"Contour angle  : {contour_angle:.2f}°\n"
        f"Rotation diff  : {rotation_diff:.2f}°\n"
        f"Centroid diff  : dx={centroid_diff[0]:.1f}, dy={centroid_diff[1]:.1f}"
    )
    ax2.axis("off")
    ax2.text(0.05, 0.5, info, transform=ax2.transAxes, fontsize=11,
             verticalalignment="center", family="monospace",
             bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8))
    ax2.set_title("Difference info")

    out_path = debug_dir / f"diff_debug_{timestamp}.png"
    plt.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"🔍 Difference debug plot saved: {out_path}")


def plot_contour_alignment(
    original_target: np.ndarray,
    reference: np.ndarray,
    centroid: Tuple,
    original_sprays: List[np.ndarray],
    workpiece: Any,
    rotated: np.ndarray,
    final: np.ndarray,
    rotation_diff: float,
    translation_diff,
    contour_orientation: Optional[float],
    spray_contour_objs: Optional[list],
    spray_fill_objs: Optional[list],
    index: int,
) -> None:
    import matplotlib.pyplot as plt

    debug_dir = _ensure_debug_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    pts_orig = _to_2d(original_target)
    pts_ref  = _to_2d(reference)
    pts_fin  = _to_2d(final)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"Alignment #{index} — rot={rotation_diff:.1f}°", fontsize=12)

    axes[0].plot(pts_orig[:, 0], pts_orig[:, 1], "b-", linewidth=2, label="Original WP")
    axes[0].plot(pts_ref[:, 0],  pts_ref[:, 1],  "r--", linewidth=1, label="Detected")
    axes[0].set_title("Before alignment")
    axes[0].set_aspect("equal")
    axes[0].legend(fontsize=8)
    axes[0].grid(True, alpha=0.3)
    axes[0].invert_yaxis()

    axes[1].plot(pts_fin[:, 0], pts_fin[:, 1], "g-", linewidth=2, label="Aligned WP")
    axes[1].plot(pts_ref[:, 0], pts_ref[:, 1],  "r--", linewidth=1, label="Detected")
    axes[1].set_title("After alignment")
    axes[1].set_aspect("equal")
    axes[1].legend(fontsize=8)
    axes[1].grid(True, alpha=0.3)
    axes[1].invert_yaxis()

    axes[2].axis("off")
    dx, dy = (translation_diff[0], translation_diff[1]) if translation_diff is not None else (0, 0)
    info = (
        f"rotation diff      : {rotation_diff:.2f}°\n"
        f"translation diff   : dx={dx:.1f}, dy={dy:.1f}\n"
        f"contour orientation: {contour_orientation:.2f}°\n" if contour_orientation is not None
        else "contour orientation: N/A\n"
    )
    axes[2].text(0.05, 0.5, info, transform=axes[2].transAxes, fontsize=10,
                 verticalalignment="center", family="monospace",
                 bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8))
    axes[2].set_title("Transform info")

    out_path = debug_dir / f"alignment_{index}_{timestamp}.png"
    plt.savefig(out_path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"🔍 Alignment debug plot saved: {out_path}")

