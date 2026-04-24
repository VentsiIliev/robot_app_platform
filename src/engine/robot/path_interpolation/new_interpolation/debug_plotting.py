import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # force non-GUI backend before pyplot import

import numpy as np
from matplotlib import pyplot as plt


def _execution_rotation_change_mask(execution_arr: np.ndarray, threshold_deg: float = 1e-6) -> np.ndarray:
    if execution_arr.ndim != 2 or execution_arr.shape[0] < 2 or execution_arr.shape[1] < 6:
        return np.zeros(execution_arr.shape[0] if execution_arr.ndim == 2 else 0, dtype=bool)

    rz_values = execution_arr[:, 5].astype(float)
    rz_delta = np.abs(np.diff(rz_values))
    mask = np.zeros(len(execution_arr), dtype=bool)
    mask[1:] = rz_delta > float(threshold_deg)
    return mask


def plot_trajectory_debug(
    raw_paths,
    curve_paths,
    sampled_paths,
    execution_paths=None,
    prepared_paths=None,
    save_dir="debug_plots",
):

    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if execution_paths is None:
            execution_paths = sampled_paths
        if prepared_paths is None:
            prepared_paths = raw_paths

        # Create figure with subplots (without 3D for compatibility)
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

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
            rotate_mask = _execution_rotation_change_mask(execution_arr)
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
                    label='Execute RZ Change' if i == 0 else '',
                )

        ax1.legend()
        ax1.axis('equal')

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
            rotate_mask = _execution_rotation_change_mask(execution_arr)
            if np.any(rotate_mask):
                rotated_points = execution_arr[rotate_mask]
                ax2.scatter(
                    rotated_points[:, 0],
                    rotated_points[:, 2],
                    s=32,
                    color='cyan',
                    edgecolors='black',
                    linewidths=0.6,
                    label='Execute RZ Change' if i == 0 else '',
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
            rotate_mask = _execution_rotation_change_mask(execution_arr)
            if np.any(rotate_mask):
                execution_idx = np.linspace(0, len(orig_arr) - 1, len(execution_arr))
                ax3.scatter(
                    execution_idx[rotate_mask],
                    execution_arr[rotate_mask, 2],
                    s=28,
                    color='cyan',
                    edgecolors='black',
                    linewidths=0.6,
                    label='Execute RZ Change' if i == 0 else '',
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

        ordered_snapshots: list[tuple[int, int, np.ndarray]] = []
        for path_index, snapshots in enumerate(motion_snapshots):
            if not snapshots:
                continue
            for step_index, shape in enumerate(snapshots):
                shape_arr = np.array(shape, dtype=float)
                if len(shape_arr) == 0:
                    continue
                ordered_snapshots.append((path_index, step_index, shape_arr))

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
        ax0.set_ylabel('Y (mm)')
        ax0.grid(True)

        ax1.set_title('Pivot Path XY')
        ax1.set_xlabel('X (mm)')
        ax1.set_ylabel('Y (mm)')
        ax1.grid(True)

        ax2.set_title('Pivot Path RZ')
        ax2.set_xlabel('Point Index')
        ax2.set_ylabel('RZ (deg)')
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
                    pivot_arr[:, 0], pivot_arr[:, 1],
                    'x-', color='magenta', linewidth=1.5, markersize=4,
                    label=f'Pivot {i+1}' if i == 0 else '',
                )
                ax2.plot(
                    np.arange(len(pivot_arr)), pivot_arr[:, 5],
                    'x-', color='magenta', linewidth=1.5, markersize=4,
                    label=f'Pivot RZ {i+1}' if i == 0 else '',
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
            ax0.scatter(
                [float(pivot_pose[0])], [float(pivot_pose[1])],
                c='red', s=80, marker='+', linewidths=2,
                label='Pivot',
            )
            ax1.scatter(
                [float(pivot_pose[0])], [float(pivot_pose[1])],
                c='red', s=80, marker='+', linewidths=2,
                label='Pivot',
            )

        ax0.legend()
        ax0.axis('equal')
        ax1.set_title('Pivot Path XY / Motion Snapshots')
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
            pivot_xy = None
            if pivot_pose and len(pivot_pose) >= 2:
                pivot_xy = (float(pivot_pose[0]), float(pivot_pose[1]))
            for flat_index, (path_index, step_index, shape) in enumerate(ordered_snapshots):
                row = 1 + flat_index // detail_cols
                col = flat_index % detail_cols
                ax = fig.add_subplot(grid[row, col])
                _plot_closed_shape(
                    ax,
                    shape,
                    title=f"Step {flat_index + 1}  P{path_index + 1}:{step_index}",
                    pivot_xy=pivot_xy,
                )

        plt.tight_layout()

        filename = f"pivot_path_debug_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
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
