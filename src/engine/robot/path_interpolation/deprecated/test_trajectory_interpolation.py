import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))
from src.engine.robot.path_interpolation.deprecated.combined_interpolation import interpolate_path_two_stage
from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import plot_trajectory_debug
def load_trajectory_from_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    trajectory = data.get('trajectory', [])
    xy_points = [[point[0], point[1]] for point in trajectory]
    return xy_points
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'trajectory_20260211_120155.json')
    print(f"Loading trajectory from: {json_path}")
    xy_points = load_trajectory_from_json(json_path)
    print(f"Loaded {len(xy_points)} points")
    xyz_points = [[x, y, 0] for x, y in xy_points]
    adaptive_spacing_mm = 5.0
    spline_density_multiplier = 2.0
    smoothing_lambda = 0.0
    print(f"\nInterpolating with:")
    print(f"  adaptive_spacing_mm: {adaptive_spacing_mm}")
    print(f"  spline_density_multiplier: {spline_density_multiplier}")
    print(f"  smoothing_lambda: {smoothing_lambda}")
    linear_result, spline_result = interpolate_path_two_stage(
        xyz_points,
        adaptive_spacing_mm=adaptive_spacing_mm,
        spline_density_multiplier=spline_density_multiplier,
        smoothing_lambda=smoothing_lambda,
        debug=True
    )
    print(f"\nResults:")
    print(f"  Original points: {len(xyz_points)}")
    print(f"  Linear interpolation: {len(linear_result)}")
    print(f"  Spline interpolation: {len(spline_result)}")
    plot_trajectory_debug(
        raw_paths=[xyz_points],
        curve_paths=[linear_result],
        sampled_paths=[spline_result],
        save_dir=os.path.join(script_dir, "debug_plots")
    )
    print(f"\nPlot saved to: {os.path.join(script_dir, 'debug_plots')}")
if __name__ == "__main__":
    main()
