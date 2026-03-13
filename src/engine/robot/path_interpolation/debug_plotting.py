import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # force non-GUI backend before pyplot import

import numpy as np
from matplotlib import pyplot as plt


def plot_trajectory_debug(original_paths, linear_paths, spline_paths, save_dir="debug_plots"):

    try:
        os.makedirs(save_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create figure with subplots (without 3D for compatibility)
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # 2D XY plot with different colors for linear and spline
        ax1.set_title('XY Trajectory (Top View)')
        ax1.set_xlabel('X (mm)')
        ax1.set_ylabel('Y (mm)')
        ax1.grid(True)

        for i, (orig, linear, spline) in enumerate(zip(original_paths, linear_paths, spline_paths)):
            orig_arr = np.array(orig)
            linear_arr = np.array(linear)
            spline_arr = np.array(spline)

            ax1.plot(orig_arr[:, 0], orig_arr[:, 1], 'o-', color='red', label=f'Original {i+1}' if i == 0 else '', markersize=8, linewidth=2, zorder=1)
            ax1.plot(linear_arr[:, 0], linear_arr[:, 1], 's', color='blue', label=f'Linear {i+1}' if i == 0 else '', markersize=4, alpha=0.6, zorder=2)
            ax1.plot(spline_arr[:, 0], spline_arr[:, 1], '.', color='green', label=f'Spline {i+1}' if i == 0 else '', markersize=2, alpha=0.5, zorder=3)

        ax1.legend()
        ax1.axis('equal')

        # XZ side view with different colors
        ax2.set_title('XZ Trajectory (Side View)')
        ax2.set_xlabel('X (mm)')
        ax2.set_ylabel('Z (mm)')
        ax2.grid(True)

        for i, (orig, linear, spline) in enumerate(zip(original_paths, linear_paths, spline_paths)):
            orig_arr = np.array(orig)
            linear_arr = np.array(linear)
            spline_arr = np.array(spline)

            ax2.plot(orig_arr[:, 0], orig_arr[:, 2], 'o-', color='red', label=f'Original {i+1}' if i == 0 else '', markersize=6, linewidth=2)
            ax2.plot(linear_arr[:, 0], linear_arr[:, 2], 's', color='blue', label=f'Linear {i+1}' if i == 0 else '', markersize=3, alpha=0.6)
            ax2.plot(spline_arr[:, 0], spline_arr[:, 2], '.', color='green', label=f'Spline {i+1}' if i == 0 else '', markersize=1, alpha=0.5)

        ax2.legend()

        # Z height profile with different colors
        ax3.set_title('Z Height Profile')
        ax3.set_xlabel('Point Index')
        ax3.set_ylabel('Z (mm)')
        ax3.grid(True)

        for i, (orig, linear, spline) in enumerate(zip(original_paths, linear_paths, spline_paths)):
            orig_arr = np.array(orig)
            linear_arr = np.array(linear)
            spline_arr = np.array(spline)

            ax3.plot(range(len(orig_arr)), orig_arr[:, 2], 'o-', color='red', label=f'Original {i+1}' if i == 0 else '', markersize=6)
            ax3.plot(np.linspace(0, len(orig_arr)-1, len(linear_arr)), linear_arr[:, 2], 's', color='blue', label=f'Linear {i+1}' if i == 0 else '', markersize=3, alpha=0.6)
            ax3.plot(np.linspace(0, len(orig_arr)-1, len(spline_arr)), spline_arr[:, 2], '.', color='green', label=f'Spline {i+1}' if i == 0 else '', markersize=2, alpha=0.5)

        ax3.legend()

        # Point count comparison with three bars
        ax4.set_title('Point Count Comparison')

        path_labels = [f'Path {i+1}' for i in range(len(original_paths))]
        orig_counts = [len(p) for p in original_paths]
        linear_counts = [len(p) for p in linear_paths]
        spline_counts = [len(p) for p in spline_paths]

        x = np.arange(len(path_labels))
        width = 0.25

        ax4.bar(x - width, orig_counts, width, label='Original', color='red', alpha=0.8)
        ax4.bar(x, linear_counts, width, label='Linear', color='blue', alpha=0.8)
        ax4.bar(x + width, spline_counts, width, label='Spline', color='green', alpha=0.8)

        ax4.set_xlabel('Path')
        ax4.set_ylabel('Number of Points')
        ax4.set_xticks(x)
        ax4.set_xticklabels(path_labels)
        ax4.legend()
        ax4.grid(True, axis='y')

        # Add value labels on bars
        for i, (orig, linear, spline) in enumerate(zip(orig_counts, linear_counts, spline_counts)):
            ax4.text(i - width, orig, str(orig), ha='center', va='bottom', fontsize=8)
            ax4.text(i, linear, str(linear), ha='center', va='bottom', fontsize=8)
            ax4.text(i + width, spline, str(spline), ha='center', va='bottom', fontsize=8)

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
