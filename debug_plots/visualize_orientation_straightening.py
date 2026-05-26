#!/usr/bin/env python3
"""
Visualization script for contour orientation straightening in pick/paint operations.
This helps debug the issue where contour orientation is slightly rotated when 
painting in Painting2 position (horizontal painting mode - xz_y_ry).
"""
import sys
import os
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyArrowPatch
from matplotlib.collections import PatchCollection

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_demo_contour():
    """Create a demo irregular contour for visualization."""
    angles = np.linspace(0, 2 * np.pi, 100)
    # Create a slightly irregular shape
    radii = 50 + 10 * np.sin(5 * angles) + 5 * np.cos(3 * angles)
    x = radii * np.cos(angles)
    y = radii * np.sin(angles)
    # Add some rotation to make it non-axis-aligned
    rotation_angle = 25.0  # degrees
    rad = np.radians(rotation_angle)
    rotated_x = x * np.cos(rad) - y * np.sin(rad)
    rotated_y = x * np.sin(rad) + y * np.cos(rad)
    return np.column_stack([rotated_x + 100, rotated_y + 100])


def compute_contour_orientation_moments(contour):
    """Compute orientation from contour central moments (cv2.moments)."""
    import cv2
    contour_arr = contour.astype(np.float32).reshape(-1, 1, 2)
    moments = cv2.moments(contour_arr)
    mu20 = float(moments.get("mu20", 0.0))
    mu11 = float(moments.get("mu11", 0.0))
    mu02 = float(moments.get("mu02", 0.0))
    if abs(mu20) < 1e-10 and abs(mu11) < 1e-10 and abs(mu02) < 1e-10:
        return 0.0
    heading = 0.5 * np.arctan2(2.0 * mu11, mu20 - mu02)
    return np.degrees(heading)


def compute_path_tangent(contour):
    """Compute the tangent direction at the first point of the contour."""
    if len(contour) < 2:
        return 0.0
    dx = contour[1][0] - contour[0][0]
    dy = contour[1][1] - contour[0][1]
    return np.degrees(np.arctan2(dy, dx))


def rotate_contour(contour, angle_deg, pivot):
    """Rotate contour around pivot point."""
    rad = np.radians(angle_deg)
    cos_r = np.cos(rad)
    sin_r = np.sin(rad)
    pivot = np.asarray(pivot)
    centered = contour - pivot
    rotated = np.column_stack([
        centered[:, 0] * cos_r - centered[:, 1] * sin_r,
        centered[:, 0] * sin_r + centered[:, 1] * cos_r
    ])
    return rotated + pivot


def straightening_analysis(contour, mode="vertical"):
    """
    Analyze how the contour should be straightened for painting.
    
    mode: "vertical" (xy_z_rz) or "horizontal" (xz_y_ry)
    """
    # Compute centroid
    centroid = np.mean(contour, axis=0)
    
    # Compute orientation from moments
    moments_rz = compute_contour_orientation_moments(contour)
    
    # Compute path tangent direction
    path_tangent = compute_path_tangent(contour)
    
    # The issue: for horizontal mode (xz_y_ry), the rotation axis is different
    # In horizontal mode, RY is the rotation that changes, not RZ
    # So we need to consider how to "straighten" the contour
    
    # Calculate the angle difference between contour axis and X-axis
    angle_diff = path_tangent - moments_rz
    
    # Normalize to -180 to 180
    while angle_diff > 180:
        angle_diff -= 360
    while angle_diff < -180:
        angle_diff += 360
    
    # For horizontal painting (xz_y_ry), the approach direction matters more
    # The contour should be oriented so that the first segment points along
    # the configured paint axis
    if mode == "horizontal":
        # In horizontal mode, we need to consider a different straightening approach
        # The rotation around Y-axis means the orientation around Z doesn't matter as much
        pass
    
    return {
        "centroid": centroid,
        "moments_rz": moments_rz,
        "path_tangent": path_tangent,
        "angle_diff": angle_diff,
        "mode": mode
    }


def visualize_orientation_straightening(contour, mode="vertical", output_path=None):
    """Create a visualization of contour orientation straightening."""
    analysis = straightening_analysis(contour, mode)
    
    centroid = analysis["centroid"]
    moments_rz = analysis["moments_rz"]
    path_tangent = analysis["path_tangent"]
    angle_diff = analysis["angle_diff"]
    
    # Create straightened contour - rotate to make path tangent horizontal
    straightened = rotate_contour(contour, -angle_diff, tuple(centroid))
    
    # Create figure with multiple subplots
    fig = plt.figure(figsize=(16, 10))
    
    # Original contour with orientation
    ax1 = fig.add_subplot(2, 3, 1)
    ax1.set_title(f"Original Contour (Mode: {mode})", fontsize=12, fontweight='bold')
    ax1.plot(contour[:, 0], contour[:, 1], 'b-', linewidth=2, label='Contour')
    ax1.scatter(centroid[0], centroid[1], c='red', s=100, marker='x', label='Centroid')
    
    # Draw orientation arrow from moments
    arrow_len = 60
    rad_mom = np.radians(moments_rz)
    ax1.arrow(centroid[0], centroid[1], 
             arrow_len * np.cos(rad_mom), arrow_len * np.sin(rad_mom),
             head_width=8, head_length=5, fc='green', ec='green', linewidth=2)
    ax1.text(centroid[0] + 70 * np.cos(rad_mom), centroid[1] + 70 * np.sin(rad_mom),
             f'Moments\n{moments_rz:.1f}°', fontsize=9, color='green')
    
    # Draw path tangent arrow
    rad_path = np.radians(path_tangent)
    ax1.arrow(centroid[0], centroid[1],
             arrow_len * np.cos(rad_path), arrow_len * np.sin(rad_path),
             head_width=8, head_length=5, fc='orange', ec='orange', linewidth=2)
    ax1.text(centroid[0] + 70 * np.cos(rad_path), centroid[1] + 70 * np.sin(rad_path),
             f'Path\n{path_tangent:.1f}°', fontsize=9, color='orange')
    
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right')
    
    # Straightened contour
    ax2 = fig.add_subplot(2, 3, 2)
    ax2.set_title(f"Straightened Contour (Angle Diff: {angle_diff:.1f}°)", fontsize=12, fontweight='bold')
    straightened_centroid = np.mean(straightened, axis=0)
    ax2.plot(straightened[:, 0], straightened[:, 1], 'g-', linewidth=2, label='Straightened')
    ax2.scatter(straightened_centroid[0], straightened_centroid[1], c='red', s=100, marker='x')
    
    # Show that path tangent is now horizontal
    ax2.axhline(y=straightened_centroid[1], color='gray', linestyle='--', alpha=0.5)
    ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper right')
    
    # Overlay comparison
    ax3 = fig.add_subplot(2, 3, 3)
    ax3.set_title("Overlay Comparison", fontsize=12, fontweight='bold')
    # Shift straightened to match original centroid for comparison
    offset = centroid - straightened_centroid
    shifted_straightened = straightened + offset
    ax3.plot(contour[:, 0], contour[:, 1], 'b-', linewidth=2, alpha=0.7, label='Original')
    ax3.plot(shifted_straightened[:, 0], shifted_straightened[:, 1], 'g--', linewidth=2, alpha=0.7, label='Straightened')
    ax3.set_aspect('equal')
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='upper right')
    
    # Orientation components analysis
    ax4 = fig.add_subplot(2, 3, 4)
    ax4.set_title("Orientation Components", fontsize=12, fontweight='bold')
    angles = [0, 90, 180, 270]
    values = [
        np.cos(np.radians(moments_rz)),
        np.sin(np.radians(moments_rz)),
        np.cos(np.radians(path_tangent)),
        np.sin(np.radians(path_tangent))
    ]
    bars = ax4.bar(['cos(mom)', 'sin(mom)', 'cos(path)', 'sin(path)'], values, color=['green', 'green', 'orange', 'orange'])
    ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax4.set_ylabel("Value")
    ax4.grid(True, alpha=0.3, axis='y')
    
    # Mode comparison
    ax5 = fig.add_subplot(2, 3, 5)
    ax5.set_title(f"Mode: {mode} - Orientation Analysis", fontsize=12, fontweight='bold')
    
    vertical_analysis = straightening_analysis(contour, "vertical")
    horizontal_analysis = straightening_analysis(contour, "horizontal")
    
    comparison_data = [
        ['Moment Orientation', f"{vertical_analysis['moments_rz']:.1f}°", f"{horizontal_analysis['moments_rz']:.1f}°"],
        ['Path Tangent', f"{vertical_analysis['path_tangent']:.1f}°", f"{horizontal_analysis['path_tangent']:.1f}°"],
        ['Angle Difference', f"{vertical_analysis['angle_diff']:.1f}°", f"{horizontal_analysis['angle_diff']:.1f}°"],
    ]
    
    ax5.axis('off')
    table = ax5.table(cellText=comparison_data, 
                      colLabels=['Property', 'Vertical (xy_z_rz)', 'Horizontal (xz_y_ry)'],
                      loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)
    
    # Info text
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.set_title("Debug Info", fontsize=12, fontweight='bold')
    info_text = f"""
    Contour Analysis:
    - Mode: {mode}
    - Centroid: ({centroid[0]:.2f}, {centroid[1]:.2f})
    - Moments Orientation: {moments_rz:.2f}°
    - Path Tangent: {path_tangent:.2f}°
    - Angle to Straighten: {angle_diff:.2f}°
    
    Note: The "slight rotation" issue in Painting2
    (horizontal mode) may be due to:
    1. The contour's moments orientation not being
       aligned with the paint axis
    2. The rotation transformation not accounting
       for the different rotation axis in horizontal
       mode (RY instead of RZ)
    """
    ax6.text(0.1, 0.5, info_text, transform=ax6.transAxes, fontsize=10,
             verticalalignment='center', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    ax6.axis('off')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Saved visualization to: {output_path}")
    else:
        plt.savefig("contour_orientation_straightening.png", dpi=150, bbox_inches='tight')
        print("Saved: contour_orientation_straightening.png")
    
    plt.close()
    return analysis


def _enhance_horizontal_straightening(points, base_rotation, target_heading):
    """Enhanced straightening for horizontal mode (mimics the fix)."""
    if len(points) < 3:
        return base_rotation
    
    # Compute the contour's principal axis using covariance
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    cov = np.dot(centered.T, centered) / len(points)
    
    # Get the principal axis
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    principal_axis = eigenvectors[:, np.argmax(eigenvalues)]
    principal_angle = float(np.degrees(np.arctan2(principal_axis[1], principal_axis[0])))
    
    # Calculate rotation to align principal axis to target
    def unwrap_degrees(ref, val):
        while val - ref > 180:
            val -= 360
        while val - ref < -180:
            val += 360
        return val
    
    principal_to_target = unwrap_degrees(0, target_heading - principal_angle)
    
    # Blend the base rotation with the principal axis alignment
    blend_factor = 0.7
    
    enhanced_rotation = base_rotation * (1 - blend_factor) + principal_to_target * blend_factor
    
    return enhanced_rotation


def analyze_pickup_paint_positions():
    """Analyze the difference between pickup and paint positions."""
    
    # Simulate different scenarios
    scenarios = [
        {"name": "Vertical Painting (PAINTING)", "mode": "vertical", "rotation": "RZ"},
        {"name": "Horizontal Painting (PAINTING2)", "mode": "horizontal", "rotation": "RY"},
    ]
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    for idx, scenario in enumerate(scenarios):
        ax = axes[idx]
        mode = scenario["mode"]
        
        # Create contour
        contour = create_demo_contour()
        
        # Analyze
        analysis = straightening_analysis(contour, mode)
        
        # Plot
        ax.set_title(scenario["name"], fontsize=12, fontweight='bold')
        
        # Original
        ax.plot(contour[:, 0], contour[:, 1], 'b-', linewidth=2, alpha=0.7, label='Original')
        
        # Straightened
        centroid = analysis["centroid"]
        angle_diff = analysis["angle_diff"]
        straightened = rotate_contour(contour, -angle_diff, tuple(centroid))
        offset = centroid - np.mean(straightened, axis=0)
        ax.plot(straightened[:, 0] + offset[0], straightened[:, 1] + offset[1], 
                'g--', linewidth=2, alpha=0.7, label='Straightened')
        
        # Show rotation axis
        if mode == "horizontal":
            ax.text(0.02, 0.98, f"Rotation axis: {scenario['rotation']}\n(around Y-axis)",
                    transform=ax.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        else:
            ax.text(0.02, 0.98, f"Rotation axis: {scenario['rotation']}\n(around Z-axis)",
                    transform=ax.transAxes, fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
        
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper right')
        ax.set_xlabel("X (mm)")
        ax.set_ylabel("Y (mm)")
    
    plt.tight_layout()
    plt.savefig("pickup_paint_position_comparison.png", dpi=150, bbox_inches='tight')
    print("Saved: pickup_paint_position_comparison.png")
    plt.close()


def visualize_fix_comparison():
    """Visualize the before/after effect of the fix for horizontal mode."""
    
    # Create a test contour with significant rotation
    np.random.seed(42)
    angles = np.linspace(0, 2 * np.pi, 80)
    radii = 40 + 8 * np.sin(6 * angles) + 4 * np.cos(4 * angles)
    x = radii * np.cos(angles)
    y = radii * np.sin(angles)
    # Add significant rotation to make the issue visible
    rotation_angle = 35.0
    rad = np.radians(rotation_angle)
    contour = np.column_stack([
        x * np.cos(rad) - y * np.sin(rad) + 120,
        x * np.sin(rad) + y * np.cos(rad) + 100
    ])
    
    # Target heading for horizontal mode
    target_heading = 0.0  # Horizontal
    
    # Original straightening (just first segment)
    original_analysis = straightening_analysis(contour, "horizontal")
    base_rotation = original_analysis["angle_diff"]
    
    # Enhanced straightening (with fix)
    enhanced_rotation = _enhance_horizontal_straightening(
        contour, base_rotation, target_heading
    )
    
    centroid = original_analysis["centroid"]
    
    # Create visualization
    fig = plt.figure(figsize=(16, 10))
    
    # Original contour
    ax1 = fig.add_subplot(2, 2, 1)
    ax1.set_title("Original Contour", fontsize=12, fontweight='bold')
    ax1.plot(contour[:, 0], contour[:, 1], 'b-', linewidth=2)
    ax1.scatter(centroid[0], centroid[1], c='red', s=80, marker='x')
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlabel("X (mm)")
    ax1.set_ylabel("Y (mm)")
    
    # Old method (base rotation only)
    ax2 = fig.add_subplot(2, 2, 2)
    ax2.set_title(f"Old Method: Base Rotation Only\n(rotation: {base_rotation:.2f}°)", 
                  fontsize=12, fontweight='bold')
    old_straightened = rotate_contour(contour, -base_rotation, tuple(centroid))
    offset = centroid - np.mean(old_straightened, axis=0)
    ax2.plot(contour[:, 0], contour[:, 1], 'b-', linewidth=2, alpha=0.5, label='Original')
    ax2.plot(old_straightened[:, 0] + offset[0], old_straightened[:, 1] + offset[1], 
             'r-', linewidth=2, label='Straightened')
    ax2.axhline(y=centroid[1], color='gray', linestyle='--', alpha=0.5)
    ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_xlabel("X (mm)")
    ax2.set_ylabel("Y (mm)")
    
    # New method (enhanced straightening)
    ax3 = fig.add_subplot(2, 2, 3)
    ax3.set_title(f"New Method: Enhanced Straightening\n(rotation: {enhanced_rotation:.2f}°)", 
                  fontsize=12, fontweight='bold')
    new_straightened = rotate_contour(contour, -enhanced_rotation, tuple(centroid))
    offset = centroid - np.mean(new_straightened, axis=0)
    ax3.plot(contour[:, 0], contour[:, 1], 'b-', linewidth=2, alpha=0.5, label='Original')
    ax3.plot(new_straightened[:, 0] + offset[0], new_straightened[:, 1] + offset[1], 
             'g-', linewidth=2, label='Straightened (Fixed)')
    ax3.axhline(y=centroid[1], color='gray', linestyle='--', alpha=0.5)
    ax3.set_aspect('equal')
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    ax3.set_xlabel("X (mm)")
    ax3.set_ylabel("Y (mm)")
    
    # Comparison overlay
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.set_title("Comparison: Old vs New", fontsize=12, fontweight='bold')
    ax4.plot(old_straightened[:, 0] + offset[0], old_straightened[:, 1] + offset[1], 
             'r-', linewidth=2, alpha=0.7, label='Old Method')
    ax4.plot(new_straightened[:, 0] + offset[0], new_straightened[:, 1] + offset[1], 
             'g-', linewidth=2, alpha=0.7, label='New Method (Fixed)')
    ax4.axhline(y=centroid[1], color='gray', linestyle='--', alpha=0.5)
    ax4.set_aspect('equal')
    ax4.grid(True, alpha=0.3)
    ax4.legend()
    ax4.set_xlabel("X (mm)")
    ax4.set_ylabel("Y (mm)")
    
    # Add info text
    improvement = abs(base_rotation - enhanced_rotation)
    fig.text(0.5, 0.02, 
             f"Rotation difference: {improvement:.2f}° | Fix applies principal axis alignment for horizontal mode",
             ha='center', fontsize=11, style='italic')
    
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig("orientation_fix_comparison.png", dpi=150, bbox_inches='tight')
    print("Saved: orientation_fix_comparison.png")
    plt.close()
    
    return {
        "base_rotation": base_rotation,
        "enhanced_rotation": enhanced_rotation,
        "improvement": improvement
    }


def main():
    parser = argparse.ArgumentParser(description="Visualize contour orientation straightening")
    parser.add_argument("--mode", choices=["vertical", "horizontal"], default="horizontal",
                       help="Painting mode (vertical=xy_z_rz, horizontal=xz_y_ry)")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--fix-comparison", action="store_true",
                       help="Show before/after comparison of the fix")
    args = parser.parse_args()
    
    print("Creating contour orientation visualization...")
    contour = create_demo_contour()
    analysis = visualize_orientation_straightening(contour, mode=args.mode, output_path=args.output)
    
    print("\n--- Analysis Results ---")
    print(f"Mode: {analysis['mode']}")
    print(f"Contour Centroid: ({analysis['centroid'][0]:.2f}, {analysis['centroid'][1]:.2f})")
    print(f"Moments-based Orientation (RZ): {analysis['moments_rz']:.2f}°")
    print(f"Path Tangent: {analysis['path_tangent']:.2f}°")
    print(f"Angle to Straighten: {analysis['angle_diff']:.2f}°")
    
    # Also create comparison visualization
    print("\nCreating pickup/paint position comparison...")
    analyze_pickup_paint_positions()
    
    # Create fix comparison if requested
    if args.fix_comparison:
        print("\nCreating fix comparison visualization...")
        result = visualize_fix_comparison()
        print(f"\n--- Fix Results ---")
        print(f"Base rotation (old): {result['base_rotation']:.2f}°")
        print(f"Enhanced rotation (new): {result['enhanced_rotation']:.2f}°")
        print(f"Improvement: {result['improvement']:.2f}°")
    
    print("\nDone!")


if __name__ == "__main__":
    main()