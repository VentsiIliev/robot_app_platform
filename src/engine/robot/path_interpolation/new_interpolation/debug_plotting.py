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

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        ax1.set_title('Pivot Path XY')
        ax1.set_xlabel('X (mm)')
        ax1.set_ylabel('Y (mm)')
        ax1.grid(True)

        ax2.set_title('Pivot Path RZ')
        ax2.set_xlabel('Point Index')
        ax2.set_ylabel('RZ (deg)')
        ax2.grid(True)

        if motion_snapshots is None:
            motion_snapshots = [None] * len(pivot_paths)

        for i, (source, pivot, snapshots) in enumerate(zip(source_paths, pivot_paths, motion_snapshots)):
            source_arr = np.array(source, dtype=float)
            pivot_arr = np.array(pivot, dtype=float)
            if len(source_arr):
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

        if pivot_pose and len(pivot_pose) >= 2:
            ax1.scatter(
                [float(pivot_pose[0])], [float(pivot_pose[1])],
                c='red', s=80, marker='+', linewidths=2,
                label='Pivot',
            )

        ax1.set_title('Pivot Path XY / Motion Snapshots')
        ax1.legend()
        ax1.axis('equal')
        ax2.legend()
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
