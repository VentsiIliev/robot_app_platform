import json
import os
from datetime import datetime

os.environ.setdefault("MPLCONFIGDIR", "/tmp/robot_app_platform_matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib
matplotlib.use("Agg")  # force non-GUI backend before pyplot import

import numpy as np
from matplotlib import pyplot as plt

_PIVOT_DETAIL_SNAPSHOT_LIMIT = 8
_PIVOT_PLOT_DPI = 110
_EXECUTION_HEADING_MARKER_THRESHOLD_DEG = 2.0


def plot_pixel_to_mm_debug(
    raw_paths,
    raw_pixel_paths=None,
    homography_paths=None,
    min_rects_mm=None,
    measurement_text=None,
    save_dir="debug_plots",
):
    """Plot robot-mm paths immediately after pixel-to-mm conversion."""
    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        fig, (ax_px, ax_xy, ax_xz, ax_counts) = plt.subplots(1, 4, figsize=(22, 5.5))

        ax_px.set_title("Input Pixel Contour")
        ax_px.set_xlabel("Image X (px)")
        ax_px.set_ylabel("Image Y (px)")
        ax_px.grid(True)

        ax_xy.set_title("Pixel To MM Only - XY")
        ax_xy.set_xlabel("X (mm)")
        ax_xy.set_ylabel("Y (mm)")
        ax_xy.grid(True)

        ax_xz.set_title("Pixel To MM Only - XZ")
        ax_xz.set_xlabel("X (mm)")
        ax_xz.set_ylabel("Z (mm)")
        ax_xz.grid(True)

        labels = []
        counts = []
        raw_pixel_paths = raw_pixel_paths or []
        homography_paths = homography_paths or []
        min_rects_mm = min_rects_mm or []
        for index, path in enumerate(raw_paths or []):
            arr = np.asarray(path, dtype=float)
            if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] < 3:
                continue

            label = f"Raw mm {index + 1}"
            labels.append(f"Path {index + 1}")
            counts.append(len(arr))

            ax_xy.plot(arr[:, 0], arr[:, 1], "o-", markersize=3, linewidth=1.5, label=label)
            ax_xy.scatter(arr[0, 0], arr[0, 1], s=70, color="green", edgecolors="black", zorder=5, label="start" if index == 0 else "")
            ax_xy.scatter(arr[-1, 0], arr[-1, 1], s=70, color="red", edgecolors="black", zorder=5, label="end" if index == 0 else "")

            ax_xz.plot(arr[:, 0], arr[:, 2], "o-", markersize=3, linewidth=1.5, label=label)
            ax_xz.scatter(arr[0, 0], arr[0, 2], s=70, color="green", edgecolors="black", zorder=5, label="start" if index == 0 else "")
            ax_xz.scatter(arr[-1, 0], arr[-1, 2], s=70, color="red", edgecolors="black", zorder=5, label="end" if index == 0 else "")

            if index < len(min_rects_mm):
                _draw_min_rect_overlay(ax_xy, min_rects_mm[index], index)

            if index < len(homography_paths):
                hom_arr = np.asarray(homography_paths[index], dtype=float)
                if hom_arr.ndim == 2 and hom_arr.shape[0] > 0 and hom_arr.shape[1] >= 3:
                    ax_xy.plot(
                        hom_arr[:, 0],
                        hom_arr[:, 1],
                        "--",
                        color="black",
                        linewidth=1.4,
                        alpha=0.8,
                        label=f"Homography only {index + 1}",
                    )
                    ax_xz.plot(
                        hom_arr[:, 0],
                        hom_arr[:, 2],
                        "--",
                        color="black",
                        linewidth=1.4,
                        alpha=0.8,
                        label=f"Homography only {index + 1}",
                    )

            if index < len(raw_pixel_paths):
                px_arr = np.asarray(raw_pixel_paths[index], dtype=float)
                if px_arr.ndim == 2 and px_arr.shape[0] > 0 and px_arr.shape[1] >= 2:
                    ax_px.plot(px_arr[:, 0], px_arr[:, 1], "o-", markersize=3, linewidth=1.5, label=f"Pixels {index + 1}")
                    ax_px.scatter(px_arr[0, 0], px_arr[0, 1], s=70, color="green", edgecolors="black", zorder=5, label="start" if index == 0 else "")
                    ax_px.scatter(px_arr[-1, 0], px_arr[-1, 1], s=70, color="red", edgecolors="black", zorder=5, label="end" if index == 0 else "")

        ax_px.axis("equal")
        ax_px.invert_yaxis()
        ax_xy.axis("equal")
        ax_xz.axis("equal")
        ax_px.legend()
        ax_xy.legend()
        ax_xz.legend()

        ax_counts.set_title("Converted Point Count")
        ax_counts.set_ylabel("Points")
        ax_counts.grid(True, axis="y")
        if counts:
            x = np.arange(len(labels))
            ax_counts.bar(x, counts, color="tab:blue", alpha=0.8)
            ax_counts.set_xticks(x)
            ax_counts.set_xticklabels(labels)
            for i, count in enumerate(counts):
                ax_counts.text(i, count, str(count), ha="center", va="bottom", fontsize=9)
        else:
            ax_counts.text(0.5, 0.5, "No raw robot-mm paths", ha="center", va="center", transform=ax_counts.transAxes)

        if measurement_text:
            ax_counts.text(
                0.5,
                0.98,
                str(measurement_text),
                ha="center",
                va="top",
                fontsize=9,
                transform=ax_counts.transAxes,
                bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "tab:purple", "alpha": 0.9},
            )

        plt.tight_layout()
        filename = f"pixel_to_mm_debug_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        print(f"✓ Saved pixel-to-mm debug plot to: {filepath}")
        plt.close(fig)
        return filepath
    except Exception as e:
        print(f"⚠️ Error creating pixel-to-mm plot: {e}")
        import traceback
        traceback.print_exc()
        return None


def plot_pixel_to_mm_strategy_comparison(
    raw_pixel_path,
    strategy_paths,
    *,
    min_rects_mm=None,
    save_dir="debug_plots",
):
    """Plot side-by-side pixel-to-mm strategy results with min-rect dimensions."""
    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        strategy_paths = strategy_paths or []
        min_rects_mm = min_rects_mm or []
        column_count = max(2, len(strategy_paths) + 1)
        fig, axes = plt.subplots(1, column_count, figsize=(6.2 * column_count, 5.8))
        axes = np.asarray(axes).reshape(-1)

        ax_px = axes[0]
        ax_px.set_title("Input Pixel Contour")
        ax_px.set_xlabel("Image X (px)")
        ax_px.set_ylabel("Image Y (px)")
        ax_px.grid(True)
        px_arr = np.asarray(raw_pixel_path or [], dtype=float)
        if px_arr.ndim == 2 and px_arr.shape[0] > 0 and px_arr.shape[1] >= 2:
            ax_px.plot(px_arr[:, 0], px_arr[:, 1], "o-", markersize=3, linewidth=1.5, label="Pixels")
            ax_px.scatter(px_arr[0, 0], px_arr[0, 1], s=70, color="green", edgecolors="black", zorder=5, label="start")
            ax_px.scatter(px_arr[-1, 0], px_arr[-1, 1], s=70, color="red", edgecolors="black", zorder=5, label="end")
        ax_px.axis("equal")
        ax_px.invert_yaxis()
        ax_px.legend()

        for index, item in enumerate(strategy_paths):
            ax = axes[index + 1]
            name = str(item.get("name", f"Strategy {index + 1}"))
            path = item.get("path") or []
            arr = np.asarray(path, dtype=float)
            ax.set_title(name)
            ax.set_xlabel("X (mm)")
            ax.set_ylabel("Y (mm)")
            ax.grid(True)
            if arr.ndim == 2 and arr.shape[0] > 0 and arr.shape[1] >= 2:
                ax.plot(arr[:, 0], arr[:, 1], "o-", markersize=3, linewidth=1.5, label=name)
                ax.scatter(arr[0, 0], arr[0, 1], s=70, color="green", edgecolors="black", zorder=5, label="start")
                ax.scatter(arr[-1, 0], arr[-1, 1], s=70, color="red", edgecolors="black", zorder=5, label="end")
                if index < len(min_rects_mm):
                    _draw_min_rect_overlay(ax, min_rects_mm[index], 0)
            else:
                ax.text(0.5, 0.5, "Unavailable", ha="center", va="center", transform=ax.transAxes)
            ax.axis("equal")
            ax.legend()

        for empty_index in range(len(strategy_paths) + 1, len(axes)):
            axes[empty_index].axis("off")

        plt.tight_layout()
        filename = f"pixel_to_mm_strategy_comparison_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches="tight")
        print(f"✓ Saved pixel-to-mm strategy comparison plot to: {filepath}")
        plt.close(fig)
        return filepath
    except Exception as e:
        print(f"⚠️ Error creating pixel-to-mm strategy comparison plot: {e}")
        import traceback
        traceback.print_exc()
        return None


def _draw_min_rect_overlay(ax, rect_info, index: int) -> None:
    if not isinstance(rect_info, dict):
        return

    corners = np.asarray(rect_info.get("corners"), dtype=float)
    if corners.ndim != 2 or corners.shape[0] != 4 or corners.shape[1] < 2:
        return

    closed = np.vstack([corners[:, :2], corners[0, :2]])
    label = "Min rect" if index == 0 else ""
    ax.plot(
        closed[:, 0],
        closed[:, 1],
        "-",
        color="tab:purple",
        linewidth=2.2,
        alpha=0.95,
        label=label,
        zorder=6,
    )

    center = rect_info.get("center")
    if center is None:
        center_xy = np.mean(corners[:, :2], axis=0)
    else:
        center_xy = np.asarray(center, dtype=float).reshape(-1)[:2]
    length_mm = float(rect_info.get("length_mm", 0.0))
    width_mm = float(rect_info.get("width_mm", 0.0))
    angle_deg = float(rect_info.get("angle_deg", 0.0))
    text = f"Min rect\n{length_mm:.1f} x {width_mm:.1f} mm\nangle {angle_deg:.1f} deg"
    ax.annotate(
        text,
        xy=(center_xy[0], center_xy[1]),
        xytext=(10, 10),
        textcoords="offset points",
        fontsize=9,
        color="tab:purple",
        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "tab:purple", "alpha": 0.85},
        zorder=7,
    )


def _execution_rotation_change_mask(
    execution_arr: np.ndarray,
    threshold_deg: float = _EXECUTION_HEADING_MARKER_THRESHOLD_DEG,
) -> np.ndarray:
    if execution_arr.ndim != 2 or execution_arr.shape[0] < 2 or execution_arr.shape[1] < 6:
        return np.zeros(execution_arr.shape[0] if execution_arr.ndim == 2 else 0, dtype=bool)

    rz_values = execution_arr[:, 5].astype(float)
    rz_delta = np.abs(np.diff(rz_values))
    mask = np.zeros(len(execution_arr), dtype=bool)
    mask[1:] = rz_delta > float(threshold_deg)
    return mask


def write_path_shape_comparison_debug(
    *,
    raw_paths,
    sampled_paths,
    execution_paths,
    save_dir="debug_plots",
):
    """Persist metrics and an overlay comparing pixel-to-mm output to move-prep paths."""
    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        reports = []
        for index, raw in enumerate(raw_paths or []):
            raw_xy = _path_xy(raw)
            sampled_xy = _path_xy(sampled_paths[index]) if index < len(sampled_paths or []) else np.empty((0, 2))
            execution_xy = _path_xy(execution_paths[index]) if index < len(execution_paths or []) else np.empty((0, 2))
            reports.append(
                {
                    "path_index": index,
                    "pixel_to_mm": _shape_metrics(raw_xy),
                    "move_prep_sampled": _shape_metrics(sampled_xy),
                    "final_execution": _shape_metrics(execution_xy),
                    "pixel_to_mm_to_move_prep_sampled": _shape_delta(raw_xy, sampled_xy),
                    "pixel_to_mm_to_final_execution": _shape_delta(raw_xy, execution_xy),
                }
            )

        json_path = os.path.join(save_dir, f"path_shape_comparison_{timestamp}.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump({"timestamp": timestamp, "paths": reports}, handle, indent=2)

        png_path = _plot_path_shape_comparison_overlay(
            raw_paths=raw_paths,
            sampled_paths=sampled_paths,
            execution_paths=execution_paths,
            reports=reports,
            save_dir=save_dir,
            timestamp=timestamp,
        )
        print(f"✓ Saved path shape comparison report to: {json_path}")
        return {"json": json_path, "png": png_path}
    except Exception as e:
        print(f"⚠️ Error creating path shape comparison report: {e}")
        import traceback
        traceback.print_exc()
        return None


def _path_xy(path) -> np.ndarray:
    arr = np.asarray([] if path is None else path, dtype=float)
    if arr.ndim != 2 or arr.shape[0] == 0 or arr.shape[1] < 2:
        return np.empty((0, 2), dtype=float)
    return arr[:, :2]


def _shape_metrics(xy: np.ndarray) -> dict:
    xy = np.asarray(xy, dtype=float)
    if xy.ndim != 2 or xy.shape[0] == 0 or xy.shape[1] < 2:
        return {
            "count": 0,
            "path_length_mm": 0.0,
            "bbox_width_mm": 0.0,
            "bbox_height_mm": 0.0,
            "min_rect_width_mm": 0.0,
            "min_rect_height_mm": 0.0,
            "min_rect_angle_deg": 0.0,
            "area_mm2": 0.0,
            "centroid": [0.0, 0.0],
        }

    mins = np.min(xy, axis=0)
    maxs = np.max(xy, axis=0)
    rect_width = 0.0
    rect_height = 0.0
    rect_angle = 0.0
    if len(xy) >= 3:
        try:
            import cv2
            rect = cv2.minAreaRect(xy.astype(np.float32).reshape(-1, 1, 2))
            (_, _), (rect_width, rect_height), rect_angle = rect
            rect_width = float(rect_width)
            rect_height = float(rect_height)
            rect_angle = float(rect_angle)
            if rect_width < rect_height:
                rect_width, rect_height = rect_height, rect_width
                rect_angle += 90.0
        except Exception:
            rect_width = float(maxs[0] - mins[0])
            rect_height = float(maxs[1] - mins[1])
            rect_angle = 0.0

    return {
        "count": int(len(xy)),
        "path_length_mm": _xy_path_length(xy),
        "bbox_width_mm": float(maxs[0] - mins[0]),
        "bbox_height_mm": float(maxs[1] - mins[1]),
        "min_rect_width_mm": float(rect_width),
        "min_rect_height_mm": float(rect_height),
        "min_rect_angle_deg": float(rect_angle),
        "area_mm2": _signed_area_abs(xy),
        "centroid": [float(np.mean(xy[:, 0])), float(np.mean(xy[:, 1]))],
    }


def _shape_delta(reference_xy: np.ndarray, candidate_xy: np.ndarray) -> dict:
    reference_metrics = _shape_metrics(reference_xy)
    candidate_metrics = _shape_metrics(candidate_xy)
    nearest = _nearest_distance_stats(reference_xy, candidate_xy)
    return {
        "count_delta": int(candidate_metrics["count"] - reference_metrics["count"]),
        "path_length_delta_mm": float(candidate_metrics["path_length_mm"] - reference_metrics["path_length_mm"]),
        "bbox_width_delta_mm": float(candidate_metrics["bbox_width_mm"] - reference_metrics["bbox_width_mm"]),
        "bbox_height_delta_mm": float(candidate_metrics["bbox_height_mm"] - reference_metrics["bbox_height_mm"]),
        "min_rect_width_delta_mm": float(candidate_metrics["min_rect_width_mm"] - reference_metrics["min_rect_width_mm"]),
        "min_rect_height_delta_mm": float(candidate_metrics["min_rect_height_mm"] - reference_metrics["min_rect_height_mm"]),
        "area_delta_mm2": float(candidate_metrics["area_mm2"] - reference_metrics["area_mm2"]),
        **nearest,
    }


def _nearest_distance_stats(reference_xy: np.ndarray, candidate_xy: np.ndarray) -> dict:
    reference_xy = np.asarray(reference_xy, dtype=float)
    candidate_xy = np.asarray(candidate_xy, dtype=float)
    if len(reference_xy) == 0 or len(candidate_xy) == 0:
        return {
            "candidate_to_reference_mean_mm": 0.0,
            "candidate_to_reference_max_mm": 0.0,
            "reference_to_candidate_mean_mm": 0.0,
            "reference_to_candidate_max_mm": 0.0,
            "symmetric_hausdorff_mm": 0.0,
        }

    cand_to_ref = _nearest_distances(candidate_xy, reference_xy)
    ref_to_cand = _nearest_distances(reference_xy, candidate_xy)
    return {
        "candidate_to_reference_mean_mm": float(np.mean(cand_to_ref)),
        "candidate_to_reference_max_mm": float(np.max(cand_to_ref)),
        "reference_to_candidate_mean_mm": float(np.mean(ref_to_cand)),
        "reference_to_candidate_max_mm": float(np.max(ref_to_cand)),
        "symmetric_hausdorff_mm": float(max(np.max(cand_to_ref), np.max(ref_to_cand))),
    }


def _nearest_distances(source_xy: np.ndarray, target_xy: np.ndarray) -> np.ndarray:
    distances = np.linalg.norm(source_xy[:, None, :] - target_xy[None, :, :], axis=2)
    return np.min(distances, axis=1)


def _xy_path_length(xy: np.ndarray) -> float:
    if len(xy) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1)))


def _signed_area_abs(xy: np.ndarray) -> float:
    if len(xy) < 3:
        return 0.0
    x = xy[:, 0]
    y = xy[:, 1]
    return 0.5 * float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _plot_path_shape_comparison_overlay(
    *,
    raw_paths,
    sampled_paths,
    execution_paths,
    reports,
    save_dir: str,
    timestamp: str,
):
    if not raw_paths:
        return None

    cols = min(3, max(1, len(raw_paths)))
    rows = int(np.ceil(len(raw_paths) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(6.4 * cols, 5.6 * rows))
    axes = np.asarray(axes).reshape(-1)

    for index, axis in enumerate(axes):
        if index >= len(raw_paths):
            axis.axis("off")
            continue
        raw_xy = _path_xy(raw_paths[index])
        sampled_xy = _path_xy(sampled_paths[index]) if index < len(sampled_paths or []) else np.empty((0, 2))
        execution_xy = _path_xy(execution_paths[index]) if index < len(execution_paths or []) else np.empty((0, 2))
        report = reports[index]
        axis.set_title(f"Path {index + 1}: pixel-to-mm vs move prep")
        axis.set_xlabel("X (mm)")
        axis.set_ylabel("Y (mm)")
        axis.grid(True, alpha=0.45)
        if len(raw_xy):
            axis.plot(raw_xy[:, 0], raw_xy[:, 1], "o-", color="red", markersize=4, linewidth=1.6, label="pixel-to-mm")
        if len(sampled_xy):
            axis.plot(sampled_xy[:, 0], sampled_xy[:, 1], ".", color="green", markersize=2, alpha=0.7, label="move prep sampled")
        if len(execution_xy):
            axis.plot(execution_xy[:, 0], execution_xy[:, 1], "x-", color="magenta", markersize=4, linewidth=1.2, label="final execution")
        delta = report["pixel_to_mm_to_final_execution"]
        axis.text(
            0.02,
            0.98,
            "final delta\n"
            f"rect {delta['min_rect_width_delta_mm']:+.3f} x {delta['min_rect_height_delta_mm']:+.3f} mm\n"
            f"length {delta['path_length_delta_mm']:+.3f} mm\n"
            f"Hausdorff {delta['symmetric_hausdorff_mm']:.3f} mm",
            transform=axis.transAxes,
            va="top",
            fontsize=8,
            bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "0.35", "alpha": 0.9},
        )
        axis.axis("equal")
        axis.legend(loc="best")

    fig.tight_layout()
    filepath = os.path.join(save_dir, f"path_shape_comparison_{timestamp}.png")
    fig.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return filepath


def plot_trajectory_debug(
    raw_paths,
    curve_paths,
    sampled_paths,
    execution_paths=None,
    prepared_paths=None,
    camera_preview_paths=None,
    save_dir="debug_plots",
    heading_marker_threshold_deg: float = _EXECUTION_HEADING_MARKER_THRESHOLD_DEG,
):

    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if execution_paths is None:
            execution_paths = sampled_paths
        if prepared_paths is None:
            prepared_paths = raw_paths
        heading_marker_threshold_deg = max(0.0, float(heading_marker_threshold_deg))
        heading_marker_label = f"Execute heading change >{heading_marker_threshold_deg:g}deg"

        has_camera_preview = bool(camera_preview_paths)
        if has_camera_preview:
            fig = plt.figure(figsize=(19, 10))
            grid = fig.add_gridspec(2, 3)
            ax1 = fig.add_subplot(grid[0, 0])
            ax2 = fig.add_subplot(grid[0, 1])
            ax3 = fig.add_subplot(grid[1, 0])
            ax4 = fig.add_subplot(grid[1, 1])
            ax5 = fig.add_subplot(grid[:, 2])
        else:
            # Create figure with subplots (without 3D for compatibility)
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
            ax5 = None

        # 2D XY plot with raw, prepared, curve, sampled, and execution path
        ax1.set_title('XY Trajectory (Top View)')
        ax1.set_xlabel('X (mm)')
        ax1.set_ylabel('Y (mm)')
        ax1.grid(True)

        for i, (raw, prepared, curve, sampled, execution) in enumerate(zip(raw_paths, prepared_paths, curve_paths, sampled_paths, execution_paths)):
            orig_arr = np.array(raw)
            pre_arr = np.array(prepared)
            linear_arr = np.array(curve)
            spline_arr = np.array(sampled)
            execution_arr = np.array(execution)

            ax1.plot(orig_arr[:, 0], orig_arr[:, 1], 'o-', color='red', label=f'Raw {i+1}' if i == 0 else '', markersize=8, linewidth=2, zorder=1)
            ax1.plot(pre_arr[:, 0], pre_arr[:, 1], '^-', color='orange', label=f'Prepared {i+1}' if i == 0 else '', markersize=4, linewidth=1.5, alpha=0.8, zorder=2)
            ax1.plot(linear_arr[:, 0], linear_arr[:, 1], 's', color='blue', label=f'Curve {i+1}' if i == 0 else '', markersize=4, alpha=0.6, zorder=3)
            ax1.plot(spline_arr[:, 0], spline_arr[:, 1], '.', color='green', label=f'Sampled {i+1}' if i == 0 else '', markersize=2, alpha=0.5, zorder=4)
            ax1.plot(execution_arr[:, 0], execution_arr[:, 1], 'x-', color='magenta', label=f'Execute {i+1}' if i == 0 else '', markersize=5, linewidth=1.5, zorder=5)
            rotate_mask = _execution_rotation_change_mask(execution_arr, heading_marker_threshold_deg)
            if np.any(rotate_mask):
                rotated_points = execution_arr[rotate_mask]
                ax1.scatter(
                    rotated_points[:, 0],
                    rotated_points[:, 1],
                    s=48,
                    color='cyan',
                    edgecolors='black',
                    linewidths=0.6,
                    zorder=6,
                    label=heading_marker_label if i == 0 else '',
                )

        ax1.legend()
        ax1.axis('equal')

        if ax5 is not None:
            ax5.set_title('Camera-Space Inverse Preview')
            ax5.set_xlabel('Image X (px)')
            ax5.set_ylabel('Image Y (px)')
            ax5.grid(True)
            camera_raw = camera_preview_paths.get("raw", [])
            camera_prepared = camera_preview_paths.get("prepared", [])
            camera_curve = camera_preview_paths.get("curve", [])
            camera_sampled = camera_preview_paths.get("sampled", [])
            camera_execution = camera_preview_paths.get("execution", [])
            for i, (raw, prepared, curve, sampled, execution) in enumerate(zip(
                camera_raw,
                camera_prepared,
                camera_curve,
                camera_sampled,
                camera_execution,
            )):
                orig_arr = np.array(raw)
                pre_arr = np.array(prepared)
                linear_arr = np.array(curve)
                spline_arr = np.array(sampled)
                execution_arr = np.array(execution)
                if len(orig_arr):
                    ax5.plot(orig_arr[:, 0], orig_arr[:, 1], 'o-', color='red', label=f'Raw {i+1}' if i == 0 else '', markersize=5, linewidth=1.5, zorder=1)
                if len(pre_arr):
                    ax5.plot(pre_arr[:, 0], pre_arr[:, 1], '^-', color='orange', label=f'Prepared {i+1}' if i == 0 else '', markersize=3, linewidth=1.2, alpha=0.8, zorder=2)
                if len(linear_arr):
                    ax5.plot(linear_arr[:, 0], linear_arr[:, 1], 's', color='blue', label=f'Curve {i+1}' if i == 0 else '', markersize=3, alpha=0.6, zorder=3)
                if len(spline_arr):
                    ax5.plot(spline_arr[:, 0], spline_arr[:, 1], '.', color='green', label=f'Sampled {i+1}' if i == 0 else '', markersize=2, alpha=0.5, zorder=4)
                if len(execution_arr):
                    ax5.plot(execution_arr[:, 0], execution_arr[:, 1], 'x-', color='magenta', label=f'Execute {i+1}' if i == 0 else '', markersize=4, linewidth=1.2, zorder=5)
            ax5.legend()
            ax5.axis('equal')
            ax5.invert_yaxis()

        # XZ side view with different colors
        ax2.set_title('XZ Trajectory (Side View)')
        ax2.set_xlabel('X (mm)')
        ax2.set_ylabel('Z (mm)')
        ax2.grid(True)

        for i, (raw, prepared, curve, sampled, execution) in enumerate(zip(raw_paths, prepared_paths, curve_paths, sampled_paths, execution_paths)):
            orig_arr = np.array(raw)
            pre_arr = np.array(prepared)
            linear_arr = np.array(curve)
            spline_arr = np.array(sampled)
            execution_arr = np.array(execution)

            ax2.plot(orig_arr[:, 0], orig_arr[:, 2], 'o-', color='red', label=f'Raw {i+1}' if i == 0 else '', markersize=6, linewidth=2)
            ax2.plot(pre_arr[:, 0], pre_arr[:, 2], '^-', color='orange', label=f'Prepared {i+1}' if i == 0 else '', markersize=3, linewidth=1.2, alpha=0.8)
            ax2.plot(linear_arr[:, 0], linear_arr[:, 2], 's', color='blue', label=f'Curve {i+1}' if i == 0 else '', markersize=3, alpha=0.6)
            ax2.plot(spline_arr[:, 0], spline_arr[:, 2], '.', color='green', label=f'Sampled {i+1}' if i == 0 else '', markersize=1, alpha=0.5)
            ax2.plot(execution_arr[:, 0], execution_arr[:, 2], 'x-', color='magenta', label=f'Execute {i+1}' if i == 0 else '', markersize=4, linewidth=1.2)
            rotate_mask = _execution_rotation_change_mask(execution_arr, heading_marker_threshold_deg)
            if np.any(rotate_mask):
                rotated_points = execution_arr[rotate_mask]
                ax2.scatter(
                    rotated_points[:, 0],
                    rotated_points[:, 2],
                    s=32,
                    color='cyan',
                    edgecolors='black',
                    linewidths=0.6,
                    label=heading_marker_label if i == 0 else '',
                )

        ax2.legend()

        # Z height profile with different colors
        ax3.set_title('Z Height Profile')
        ax3.set_xlabel('Point Index')
        ax3.set_ylabel('Z (mm)')
        ax3.grid(True)

        for i, (raw, prepared, curve, sampled, execution) in enumerate(zip(raw_paths, prepared_paths, curve_paths, sampled_paths, execution_paths)):
            orig_arr = np.array(raw)
            pre_arr = np.array(prepared)
            linear_arr = np.array(curve)
            spline_arr = np.array(sampled)
            execution_arr = np.array(execution)

            ax3.plot(range(len(orig_arr)), orig_arr[:, 2], 'o-', color='red', label=f'Raw {i+1}' if i == 0 else '', markersize=6)
            ax3.plot(np.linspace(0, len(orig_arr)-1, len(pre_arr)), pre_arr[:, 2], '^-', color='orange', label=f'Prepared {i+1}' if i == 0 else '', markersize=3, linewidth=1.2, alpha=0.8)
            ax3.plot(np.linspace(0, len(orig_arr)-1, len(linear_arr)), linear_arr[:, 2], 's', color='blue', label=f'Curve {i+1}' if i == 0 else '', markersize=3, alpha=0.6)
            ax3.plot(np.linspace(0, len(orig_arr)-1, len(spline_arr)), spline_arr[:, 2], '.', color='green', label=f'Sampled {i+1}' if i == 0 else '', markersize=2, alpha=0.5)
            ax3.plot(np.linspace(0, len(orig_arr)-1, len(execution_arr)), execution_arr[:, 2], 'x-', color='magenta', label=f'Execute {i+1}' if i == 0 else '', markersize=4, linewidth=1.2)
            rotate_mask = _execution_rotation_change_mask(execution_arr, heading_marker_threshold_deg)
            if np.any(rotate_mask):
                execution_idx = np.linspace(0, len(orig_arr) - 1, len(execution_arr))
                ax3.scatter(
                    execution_idx[rotate_mask],
                    execution_arr[rotate_mask, 2],
                    s=28,
                    color='cyan',
                    edgecolors='black',
                    linewidths=0.6,
                    label=heading_marker_label if i == 0 else '',
                )

        ax3.legend()

        # Point count comparison with three bars
        ax4.set_title('Point Count Comparison')

        path_labels = [f'Path {i+1}' for i in range(len(raw_paths))]
        orig_counts = [len(p) for p in raw_paths]
        pre_counts = [len(p) for p in prepared_paths]
        linear_counts = [len(p) for p in curve_paths]
        spline_counts = [len(p) for p in sampled_paths]
        execution_counts = [len(p) for p in execution_paths]

        x = np.arange(len(path_labels))
        width = 0.16

        ax4.bar(x - 2 * width, orig_counts, width, label='Raw', color='red', alpha=0.8)
        ax4.bar(x - width, pre_counts, width, label='Prepared', color='orange', alpha=0.8)
        ax4.bar(x, linear_counts, width, label='Curve', color='blue', alpha=0.8)
        ax4.bar(x + width, spline_counts, width, label='Sampled', color='green', alpha=0.8)
        ax4.bar(x + 2 * width, execution_counts, width, label='Execute', color='magenta', alpha=0.8)

        ax4.set_xlabel('Path')
        ax4.set_ylabel('Number of Points')
        ax4.set_xticks(x)
        ax4.set_xticklabels(path_labels)
        ax4.legend()
        ax4.grid(True, axis='y')

        # Add value labels on bars
        for i, (orig, pre, linear, spline, execution) in enumerate(zip(orig_counts, pre_counts, linear_counts, spline_counts, execution_counts)):
            ax4.text(i - 2 * width, orig, str(orig), ha='center', va='bottom', fontsize=8)
            ax4.text(i - width, pre, str(pre), ha='center', va='bottom', fontsize=8)
            ax4.text(i, linear, str(linear), ha='center', va='bottom', fontsize=8)
            ax4.text(i + width, spline, str(spline), ha='center', va='bottom', fontsize=8)
            ax4.text(i + 2 * width, execution, str(execution), ha='center', va='bottom', fontsize=8)

        plt.tight_layout()

        # Save plot
        filename = f"trajectory_debug_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        print(f"✓ Saved trajectory debug plot to: {filepath}")
        plt.close()

        return filepath

    except Exception as e:
        print(f"⚠️ Error creating plot: {e}")
        import traceback
        traceback.print_exc()
        return None


def plot_pivot_path_debug(
    source_paths,
    pivot_paths,
    pivot_pose,
    motion_snapshots=None,
    save_dir="debug_plots",
):
    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if motion_snapshots is None:
            motion_snapshots = [None] * len(pivot_paths)

        def _infer_projected_plane_indices(paths) -> tuple[int, int]:
            """Infer whether projected pivot motion is in XY or XZ."""
            for path in paths or []:
                arr = np.array(path, dtype=float)
                if arr.ndim != 2 or arr.shape[1] < 3 or len(arr) < 2:
                    continue
                y_span = float(np.ptp(arr[:, 1]))
                z_span = float(np.ptp(arr[:, 2]))
                if z_span > max(1e-6, y_span * 5.0):
                    return 0, 2
            return 0, 1

        planar_i, planar_j = _infer_projected_plane_indices(pivot_paths)
        rotation_i = 4 if (planar_i, planar_j) == (0, 2) else 5
        planar_label = "XZ" if (planar_i, planar_j) == (0, 2) else "XY"
        rotation_label = "RY" if rotation_i == 4 else "RZ"

        ordered_snapshots: list[tuple[int, int, np.ndarray]] = []
        for path_index, snapshots in enumerate(motion_snapshots):
            if not snapshots:
                continue
            snapshot_count = len(snapshots)
            if snapshot_count <= _PIVOT_DETAIL_SNAPSHOT_LIMIT:
                detail_indices = list(range(snapshot_count))
            else:
                sampled = np.linspace(0, snapshot_count - 1, _PIVOT_DETAIL_SNAPSHOT_LIMIT, dtype=int)
                detail_indices = sorted({0, 1, *[int(index) for index in sampled]})
                if len(detail_indices) > _PIVOT_DETAIL_SNAPSHOT_LIMIT:
                    detail_indices = detail_indices[:2] + detail_indices[-(_PIVOT_DETAIL_SNAPSHOT_LIMIT - 2):]
            for step_index in detail_indices:
                shape = snapshots[int(step_index)]
                shape_arr = np.array(shape, dtype=float)
                if len(shape_arr) == 0:
                    continue
                ordered_snapshots.append((path_index, int(step_index), shape_arr))

        detail_cols = 4
        detail_rows = max(1, int(np.ceil(len(ordered_snapshots) / detail_cols))) if ordered_snapshots else 0
        total_rows = 1 + detail_rows
        fig = plt.figure(figsize=(19, 6 + 3.6 * detail_rows))
        grid = fig.add_gridspec(total_rows, 4)

        ax0 = fig.add_subplot(grid[0, 0])
        ax1 = fig.add_subplot(grid[0, 1:3])
        ax2 = fig.add_subplot(grid[0, 3])

        ax0.set_title('Pickup To Pivot Alignment')
        ax0.set_xlabel('X (mm)')
        ax0.set_ylabel(f"{'Z' if planar_j == 2 else 'Y'} (mm)")
        ax0.grid(True)

        ax1.set_title(f'Pivot Path {planar_label}')
        ax1.set_xlabel('X (mm)')
        ax1.set_ylabel(f"{'Z' if planar_j == 2 else 'Y'} (mm)")
        ax1.grid(True)

        ax2.set_title(f'Pivot Path {rotation_label}')
        ax2.set_xlabel('Point Index')
        ax2.set_ylabel(f'{rotation_label} (deg)')
        ax2.grid(True)

        for i, (source, pivot, snapshots) in enumerate(zip(source_paths, pivot_paths, motion_snapshots)):
            source_arr = np.array(source, dtype=float)
            pivot_arr = np.array(pivot, dtype=float)
            if len(source_arr):
                ax0.plot(
                    source_arr[:, 0], source_arr[:, 1],
                    'o-', color='blue', alpha=0.75, markersize=3,
                    label=f'Original {i+1}' if i == 0 else '',
                )
                ax1.plot(
                    source_arr[:, 0], source_arr[:, 1],
                    'o-', color='blue', alpha=0.6, markersize=3,
                    label=f'Source {i+1}' if i == 0 else '',
                )
            if len(pivot_arr):
                ax1.plot(
                    pivot_arr[:, planar_i], pivot_arr[:, planar_j],
                    'x-', color='magenta', linewidth=1.5, markersize=4,
                    label=f'Pivot {i+1}' if i == 0 else '',
                )
                if len(pivot_arr) >= 3:
                    ax1.annotate(
                        '',
                        xy=(pivot_arr[2, planar_i], pivot_arr[2, planar_j]),
                        xytext=(pivot_arr[0, planar_i], pivot_arr[0, planar_j]),
                        arrowprops=dict(
                            arrowstyle='->', color='darkmagenta',
                            linewidth=2.5, shrinkA=6, shrinkB=6,
                        ),
                        zorder=9,
                    )
                for pt_idx in range(min(4, len(pivot_arr))):
                    ax1.annotate(
                        str(pt_idx),
                        (pivot_arr[pt_idx, planar_i], pivot_arr[pt_idx, planar_j]),
                        textcoords='offset points', xytext=(4, 4),
                        fontsize=7, color='darkmagenta', fontweight='bold',
                        zorder=10,
                    )
                ax2.plot(
                    np.arange(len(pivot_arr)), pivot_arr[:, rotation_i],
                    'x-', color='magenta', linewidth=1.5, markersize=4,
                    label=f'Pivot {rotation_label} {i+1}' if i == 0 else '',
                )
            if snapshots:
                first_shape = np.array(snapshots[0], dtype=float)
                if len(first_shape):
                    ax0.plot(
                        first_shape[:, 0], first_shape[:, 1],
                        'o-', color='green', alpha=0.85, markersize=3,
                        label=f'Aligned To Pivot {i+1}' if i == 0 else '',
                    )
                    ax0.plot(
                        [first_shape[-1, 0], first_shape[0, 0]],
                        [first_shape[-1, 1], first_shape[0, 1]],
                        '-', color='green', linewidth=1.2, alpha=0.85,
                    )
                    ax0.scatter(
                        [first_shape[0, 0]], [first_shape[0, 1]],
                        c='orange', s=90, marker='*',
                        edgecolors='black', linewidths=0.8,
                        label='Initial Contact Point' if i == 0 else '',
                        zorder=8,
                    )

                sample_count = min(8, len(snapshots))
                sample_indices = np.linspace(0, len(snapshots) - 1, sample_count, dtype=int)
                for sample_idx, snapshot_index in enumerate(sample_indices):
                    shape = np.array(snapshots[int(snapshot_index)], dtype=float)
                    if len(shape) == 0:
                        continue
                    alpha = 0.15 + 0.65 * (sample_idx / max(sample_count - 1, 1))
                    ax1.plot(
                        shape[:, 0], shape[:, 1],
                        '-', color='black', linewidth=1.0, alpha=alpha,
                    )
                    ax1.plot(
                        [shape[-1, 0], shape[0, 0]],
                        [shape[-1, 1], shape[0, 1]],
                        '-', color='black', linewidth=1.0, alpha=alpha,
                    )
                    ax1.scatter(
                        [shape[0, 0]], [shape[0, 1]],
                        c='orange', s=24, marker='o', alpha=alpha,
                        label='Pivot Contact Point' if i == 0 and sample_idx == 0 else '',
                        zorder=7,
                    )

        if pivot_pose and len(pivot_pose) >= 2:
            pivot_plot_xy = None
            if len(pivot_pose) > max(planar_i, planar_j):
                pivot_plot_xy = (float(pivot_pose[planar_i]), float(pivot_pose[planar_j]))
        else:
            pivot_plot_xy = None

        if pivot_plot_xy is not None:
            ax0.scatter(
                [pivot_plot_xy[0]], [pivot_plot_xy[1]],
                c='red', s=80, marker='+', linewidths=2,
                label='Pivot',
            )
            ax1.scatter(
                [pivot_plot_xy[0]], [pivot_plot_xy[1]],
                c='red', s=80, marker='+', linewidths=2,
                label='Pivot',
            )

        ax0.legend()
        ax0.axis('equal')
        ax1.set_title(f'Pivot Path {planar_label} / Motion Snapshots')
        ax1.legend()
        ax1.axis('equal')
        ax2.legend()

        def _plot_closed_shape(ax, shape: np.ndarray, *, title: str, pivot_xy=None) -> None:
            if len(shape) == 0:
                ax.set_title(title)
                ax.grid(True)
                return
            ax.plot(shape[:, 0], shape[:, 1], '-', color='black', linewidth=1.1)
            ax.plot(
                [shape[-1, 0], shape[0, 0]],
                [shape[-1, 1], shape[0, 1]],
                '-', color='black', linewidth=1.1,
            )
            ax.scatter(
                [shape[0, 0]], [shape[0, 1]],
                c='orange', s=42, marker='o',
                edgecolors='black', linewidths=0.6, zorder=5,
            )
            if pivot_xy is not None:
                ax.scatter(
                    [float(pivot_xy[0])], [float(pivot_xy[1])],
                    c='red', s=55, marker='+', linewidths=1.8, zorder=6,
                )
            ax.set_title(title)
            ax.grid(True)
            ax.axis('equal')

        if ordered_snapshots:
            for flat_index, (path_index, step_index, shape) in enumerate(ordered_snapshots):
                row = 1 + flat_index // detail_cols
                col = flat_index % detail_cols
                ax = fig.add_subplot(grid[row, col])
                _plot_closed_shape(
                    ax,
                    shape,
                    title=f"Step {flat_index + 1}  P{path_index + 1}:{step_index}",
                    pivot_xy=pivot_plot_xy,
                )

        plt.tight_layout()

        filename = f"pivot_path_debug_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        plt.savefig(filepath, dpi=_PIVOT_PLOT_DPI, bbox_inches='tight')
        print(f"✓ Saved pivot path debug plot to: {filepath}")
        plt.close()
        return filepath
    except Exception as e:
        print(f"⚠️ Error creating pivot plot: {e}")
        import traceback
        traceback.print_exc()
        return None


def plot_workpiece_alignment_debug(
    original_contour,
    aligned_contour,
    save_dir="debug_plots",
):
    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        original = np.asarray(original_contour, dtype=float)
        aligned = np.asarray(aligned_contour, dtype=float)
        if original.ndim == 3 and original.shape[1] == 1:
            original = original[:, 0, :]
        if aligned.ndim == 3 and aligned.shape[1] == 1:
            aligned = aligned[:, 0, :]
        if original.ndim != 2 or aligned.ndim != 2 or original.shape[1] < 2 or aligned.shape[1] < 2:
            return None

        original = original[:, :2]
        aligned = aligned[:, :2]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        fig.suptitle("Workpiece Orientation: Original vs Aligned")

        def _plot(ax, points, title, color):
            if len(points) == 0:
                ax.set_title(title)
                ax.grid(True)
                return
            closed = points
            if np.linalg.norm(points[0] - points[-1]) > 1e-9:
                closed = np.vstack([points, points[:1]])
            ax.plot(closed[:, 0], closed[:, 1], 'o-', color=color, markersize=3, linewidth=1.5)
            ax.scatter([points[0, 0]], [points[0, 1]], c='orange', s=60, marker='*', edgecolors='black', linewidths=0.8, label='Start')
            centroid = np.mean(points, axis=0)
            ax.scatter([centroid[0]], [centroid[1]], c='black', s=24, marker='x', label='Centroid')
            ax.set_title(title)
            ax.set_xlabel("X (px)")
            ax.set_ylabel("Y (px)")
            ax.grid(True)
            ax.axis('equal')
            ax.legend()

        _plot(ax1, original, "Original Orientation", "blue")
        _plot(ax2, aligned, "Aligned Orientation", "magenta")

        plt.tight_layout()
        filename = f"workpiece_alignment_debug_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        print(f"✓ Saved workpiece alignment debug plot to: {filepath}")
        plt.close()
        return filepath
    except Exception as e:
        print(f"⚠️ Error creating workpiece alignment plot: {e}")
        import traceback
        traceback.print_exc()
        return None
