import logging
import time
import numpy as np
import cv2
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from scipy.interpolate import griddata

from modules.VisionSystem.laser_detection.height_measuring import HeightMeasuringService
from modules.VisionSystem.laser_detection.laser_detection_service import LaserDetectionService
from modules.VisionSystem.laser_detection.laser_detector import LaserDetector, LaserDetectionConfig
from modules.VisionSystem.laser_detection.utils import init_vision_service, init_robot_service
from modules.shared.tools.Laser import Laser
from modules.utils import utils

_logger = logging.getLogger(__name__)

# Window name for visualization
WINDOW_NAME = "Laser Height Measurement - Live View"

if __name__ == "__main__":


    vs = init_vision_service()
    rs = init_robot_service()
    rs.move_to_calibration_position()
    ld = LaserDetector(LaserDetectionConfig())
    lds = LaserDetectionService(detector=ld, laser=Laser(), vision_service=vs)
    hms = HeightMeasuringService(laser_detection_service=lds, robot_service=rs)
    chessboard_width = vs.camera_settings.get_chessboard_width()
    chessboard_height = vs.camera_settings.get_chessboard_height()
    square_size_mm = vs.camera_settings.get_square_size_mm()

    # Create visualization window
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 1280, 720)

    def draw_status_overlay(frame, status_text, color=(0, 255, 0)):
        """Draw status overlay on frame"""
        display = frame.copy()
        # Add semi-transparent overlay at top
        overlay = display.copy()
        cv2.rectangle(overlay, (0, 0), (display.shape[1], 60), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, display, 0.4, 0, display)

        # Add status text
        cv2.putText(display, status_text, (10, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 2)
        return display

    def find_chessboard():
        """Find chessboard with live visualization"""
        _logger.info("Searching for chessboard...")


        while True:
            frame = vs.latest_frame
            if frame is None:
                _logger.info(f"Waiting for camera frame...")

                time.sleep(0.1)
                continue

            # Try to find chessboard
            found, corners = cv2.findChessboardCorners(frame, (chessboard_width, chessboard_height), None)

            # Create display frame
            display = frame.copy()

            if found:
                _logger.info("Chessboard found.")

                # Draw chessboard corners
                cv2.drawChessboardCorners(display, (chessboard_width, chessboard_height), corners, found)

                # Subpixel refinement
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                           criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))

                # Show success message
                display = draw_status_overlay(display, "Chessboard Found! Processing...", (0, 255, 0))
                cv2.imshow(WINDOW_NAME, display)
                cv2.waitKey(500)  # Show for 500ms

                return corners
            else:
                # Show searching status
                display = draw_status_overlay(display, "Searching for chessboard...", (0, 165, 255))
                cv2.imshow(WINDOW_NAME, display)

                key = cv2.waitKey(100) & 0xFF
                if key == 27:  # ESC to exit
                    _logger.info("Chessboard search cancelled.")

                    return None


    def downsample_chessboard_corners(corners, target_points=50):
        """
        Reduce chessboard corners to ~target_points evenly distributed.
        Strategy:
            - corners come ordered row-major from findChessboardCorners
            - compute stride to pick evenly spaced points
        """
        N = len(corners)
        if N <= target_points:
            return corners  # no reduction needed

        stride = N / target_points
        idxs = (np.arange(target_points) * stride).astype(int)
        idxs = np.clip(idxs, 0, N - 1)

        return corners[idxs]


    def downsample_chessboard_corners_safe(corners, board_width, board_height, target_points=150):
        """
        Downsample chessboard corners but exclude the last 5 rows.

        Parameters:
            corners: np.array of shape (N,1,2) from findChessboardCorners
            board_width: number of inner corners per row
            board_height: number of inner corners per column
            target_points: desired number after downsampling

        Returns:
            Reduced set of corners (<= target_points)
        """

        import numpy as np

        # Number of rows to keep
        keep_rows = board_height - 5
        if keep_rows <= 0:
            raise ValueError("Cannot remove last 5 rows; board height too small")

        # Convert to (row, col) indexing
        N = len(corners)
        if N != board_width * board_height:
            raise ValueError("Corner count does not match given board dimensions")

        corners_reshaped = corners.reshape(board_height, board_width, 1, 2)

        # Keep only the first (board_height - 5) rows
        usable = corners_reshaped[:keep_rows].reshape(-1, 1, 2)

        M = len(usable)
        if M <= target_points:
            return usable  # no further reduction needed

        # Downsample evenly
        stride = M / target_points
        idxs = (np.arange(target_points) * stride).astype(int)
        idxs = np.clip(idxs, 0, M - 1)

        return usable[idxs]


    def extract_4_chessboard_corners_safe(corners, chessboard_width, chessboard_height):
        """
        Extract 4 points in order:
            1 = top-left
            3 = bottom-left
            2 = top-right
            4 = bottom-right moved 5 rows upward

        The last point becomes:
            row = (h - 1 - 5)
            col = (w - 1)
        """

        w = chessboard_width
        h = chessboard_height
        N = w * h

        if len(corners) != N:
            _logger.error(f"Error: expected {N} corners but got {len(corners)}")

            return corners  # fallback

        corners = corners.reshape(-1, 2)

        # Corner indices
        idx_top_left = 0
        idx_top_right = w - 1
        idx_bottom_left = (h - 1) * w

        # Move last point 5 rows up
        safe_row = max(0, (h - 1 - 5))  # safety clamp
        idx_bottom_right_safe = safe_row * w + (w - 1)

        selected = np.array([
            corners[idx_top_left],  # 1  top-left
            corners[idx_bottom_left],  # 3  bottom-left
            corners[idx_top_right],  # 2  top-right
            corners[idx_bottom_right_safe]  # 4  bottom-right (5 rows up)
        ], dtype=np.float32)

        return selected.reshape(-1, 1, 2)


    def visualize_height_map_3d(height_map, measurements):
        """
        Display a SINGLE 3D depth map plot.
        """
        # Extract points
        points = list(height_map.keys())
        x = np.array([p[0] for p in points])
        y = np.array([p[1] for p in points])
        z = np.array([height_map[p] for p in points])

        # Create interpolation grid
        grid_res = 80
        xi = np.linspace(x.min(), x.max(), grid_res)
        yi = np.linspace(y.min(), y.max(), grid_res)
        XI, YI = np.meshgrid(xi, yi)

        ZI = griddata((x, y), z, (XI, YI), method='cubic')

        # Plot a single figure
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        fig.suptitle("3D Depth Map", fontsize=16, fontweight='bold')

        # Surface
        surf = ax.plot_surface(
            XI, YI, ZI,
            cmap='viridis',
            linewidth=0,
            antialiased=True,
            alpha=0.95
        )

        # Overlay measured points
        ax.scatter(x, y, z, c='red', s=40, edgecolors='black')

        # Labels
        ax.set_xlabel("X (mm)", fontweight='bold')
        ax.set_ylabel("Y (mm)", fontweight='bold')
        ax.set_zlabel("Height (mm)", fontweight='bold')

        plt.colorbar(surf, ax=ax, shrink=0.6, label="Height (mm)")

        # Save
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"height_depthmap_{timestamp}.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        _logger.info(f"3D depth map saved to {filename}")


        plt.show()


    def convert_chessboard_corners_to_robot_points(corners, cam_to_robot_transform, x_offset, y_offset, dynamic_offset_config):
        """Convert chessboard corners from pixel coordinates to robot coordinates."""
        # Reshape corners to format expected by applyTransformation
        # corners shape is (N, 1, 2), we need list of contours
        corners_reshaped = corners.reshape(-1, 2)

        # applyTransformation expects a list of contours (each contour is list of points)
        # We'll treat all corners as a single contour
        contours = [corners_reshaped]

        # Apply transformation
        transformed_contours = utils.applyTransformation(
            cam_to_robot_transform,
            contours,
            apply_transducer_offset=True,
            x_offset=x_offset,
            y_offset=y_offset,
            dynamic_offsets_config=dynamic_offset_config
        )

        # Extract transformed points (first contour, all points)
        if transformed_contours and len(transformed_contours) > 0:
            # Convert to numpy array for easier indexing
            transformed = np.array(transformed_contours[0])
        else:
            transformed = np.array([])

        return transformed

    # Find chessboard with live visualization
    chessboard_corners_pixels = None
    while True:
        frame = vs.latest_frame
        if frame is None:
            _logger.info(f"Waiting for camera frame...")

            time.sleep(0.1)
            continue

        corners = find_chessboard()
        if corners is None:
            _logger.error("Chessboard search cancelled or failed.")

            cv2.destroyAllWindows()
            exit(0)
        reduced_corners = downsample_chessboard_corners_safe(
            corners,
            chessboard_width,
            chessboard_height
        )
        chessboard_corners_pixels = reduced_corners
        break

    # Convert corners to robot coordinates
    transformed = convert_chessboard_corners_to_robot_points(
        chessboard_corners_pixels,
        vs.cameraToRobotMatrix,
        x_offset=0,
        y_offset=0,
        dynamic_offset_config=None
    )

    _logger.info(f"\nStarting height measurement for {len(transformed)} points...")

    _logger.info("Press ESC to exit at any time\n")


    # Measure height at each transformed point with live visualization
    measurements = []
    height_map = {}  # Dictionary to store (x, y) -> height mapping
    num_iterations = 3  # Number of times to repeat the full sequence
    all_iterations = []  # List to store each full iteration result
    height_map_mean = {}  # Dictionary for average height per point

    _logger.info(f"\nStarting height measurement for {len(transformed)} points per iteration...")

    _logger.info(f"Press ESC to exit at any time\n")


    for iteration in range(num_iterations):
        _logger.info(f"\n=== Iteration {iteration + 1}/{num_iterations} ===")

        iteration_measurements = []  # store measurements for this iteration

        for idx, p in enumerate(transformed):
            x = float(p[0][0])
            y = float(p[0][1])

            _logger.info(f"\n[{idx + 1}/{len(transformed)}] Moving to position ({x:.2f}, {y:.2f})")


            # Show moving status
            frame = vs.latest_frame
            if frame is not None:
                display = draw_status_overlay(frame, f"Iter {iteration + 1} - Point {idx + 1}/{len(transformed)}",
                                              (255, 165, 0))
                cv2.imshow(WINDOW_NAME, display)
                cv2.waitKey(1)

            # Measure height
            height, _ = hms.measure_at(x=x, y=y)
            robot_pos = rs.get_current_position()

            _logger.info(f"  Robot: X={robot_pos[0]:.2f}, Y={robot_pos[1]:.2f}, Z={robot_pos[2]:.2f}")

            _logger.error(f"  Measured Height: {height:.2f} mm" if height is not None else "  Measurement FAILED")


            # Store measurement for this iteration
            iteration_measurements.append({
                'index': idx + 1,
                'target_xy': (x, y),
                'robot_pos': robot_pos,
                'height_mm': height
            })

            # Update live visualization
            frame = vs.latest_frame
            if frame is not None:
                display = frame.copy()
                info_y = 70
                line_height = 30
                overlay = display.copy()
                cv2.rectangle(overlay, (0, 60), (500, 60 + line_height * 5), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.7, display, 0.3, 0, display)

                cv2.putText(display, f"Iter {iteration + 1}/{num_iterations} - Point {idx + 1}/{len(transformed)}",
                            (10, info_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                info_y += line_height

                if height is not None:
                    cv2.putText(display, f"Height: {height:.2f} mm", (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                (0, 255, 0), 2)
                else:
                    cv2.putText(display, "Height: FAILED", (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                info_y += line_height

                cv2.putText(display, f"Robot: ({robot_pos[0]:.1f}, {robot_pos[1]:.1f}, {robot_pos[2]:.1f})",
                            (10, info_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                info_y += line_height

                cv2.putText(display, "Press ESC to exit", (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128),
                            1)

                # Draw center crosshair
                h, w = display.shape[:2]
                cv2.line(display, (w // 2 - 10, h // 2), (w // 2 + 10, h // 2), (255, 0, 0), 2)
                cv2.line(display, (w // 2, h // 2 - 10), (w // 2, h // 2 + 10), (255, 0, 0), 2)

                cv2.imshow(WINDOW_NAME, display)
                key = cv2.waitKey(500) & 0xFF
                if key == 27:
                    _logger.info("\nMeasurement interrupted by user.")

                    break

        all_iterations.append(iteration_measurements)

    # After all iterations: analyze consistency
    _logger.info("\n" + "=" * 60)

    _logger.info("MEASUREMENT CONSISTENCY REPORT")

    _logger.info("=" * 60)


    for idx in range(len(transformed)):
        heights_per_point = []
        for iteration_measurements in all_iterations:
            h = iteration_measurements[idx]['height_mm']
            if h is not None:
                heights_per_point.append(h)

        if heights_per_point:
            mean_h = np.mean(heights_per_point)
            std_h = np.std(heights_per_point)
            min_h = np.min(heights_per_point)
            max_h = np.max(heights_per_point)
            _logger.info(f"Point {idx + 1}: Mean={mean_h:.2f}, Std={std_h:.2f}, Min={min_h:.2f}, Max={max_h:.2f} mm")

            height_map_mean[tuple(transformed[idx][0])] = mean_h
        else:
            _logger.info(f"Point {idx + 1}: No successful measurements")


    # 3D visualization using mean heights
    if height_map_mean:
        _logger.info("\nGenerating 3D visualization of mean heights...")

        visualize_height_map_3d(height_map_mean, all_iterations)
    else:
        _logger.info("\nNo successful measurements to visualize.")

        cv2.waitKey(0)

    cv2.destroyAllWindows()



