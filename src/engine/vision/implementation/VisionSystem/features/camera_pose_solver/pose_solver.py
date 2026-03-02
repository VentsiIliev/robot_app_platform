import logging
from dataclasses import dataclass
import numpy as np
import cv2

from core.services.vision import VisionService
from modules.VisionSystem.calibration.cameraCalibration.CameraCalibrationService import CameraCalibrationService
from modules.VisionSystem.camera_pose_solver.helpers import print_pose_explained

_logger = logging.getLogger(__name__)


@dataclass
class PnPConfig:
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray # default zero distortion
    units: str = "mm"  # "mm" or "m" - what units object points are expressed in


class CameraPoseSolver:
    def __init__(self, config: PnPConfig):
        self.camera_matrix = config.camera_matrix.astype(np.float64)
        self.dist_coeffs = config.dist_coeffs.astype(np.float64)
        self.units = config.units

    def solve_pnp(self, object_points: np.ndarray, image_points: np.ndarray, flags=cv2.SOLVEPNP_ITERATIVE):
        """
        Solve PnP for a given set of 3D object points and corresponding 2D image points.

        Args:
            object_points (np.ndarray): Nx3 array of 3D points in the object frame (same units as self.units).
            image_points (np.ndarray): Nx2 array of 2D points in image coordinates.
            flags: cv2 solvePnP flag

        Returns:
            rvec (np.ndarray): Rotation vector (3x1)
            tvec (np.ndarray): Translation vector (3x1)
            pose_matrix (np.ndarray): 4x4 homogeneous transformation matrix
            reproj_error (float): RMS reprojection error in pixels
        """
        # basic checks
        if object_points is None or image_points is None:
            raise ValueError("object_points and image_points must be provided")

        object_points = np.asarray(object_points, dtype=np.float64).reshape(-1, 3)
        image_points = np.asarray(image_points, dtype=np.float64).reshape(-1, 2)

        if object_points.shape[0] != image_points.shape[0]:
            raise ValueError(f"Points count mismatch: object_points={object_points.shape[0]} "
                             f"image_points={image_points.shape[0]}")

        # cv2.solvePnP expects Nx3 and Nx2
        success, rvec, tvec = cv2.solvePnP(object_points, image_points,
                                           self.camera_matrix,
                                           self.dist_coeffs,
                                           flags=flags)
        if not success:
            raise RuntimeError("PnP solution failed")

        # convert rotation vector to matrix
        R, _ = cv2.Rodrigues(rvec)

        # build pose matrix (camera pose in object frame: transform object->camera)
        pose_matrix = np.eye(4, dtype=np.float64)
        pose_matrix[:3, :3] = R
        pose_matrix[:3, 3] = tvec.flatten()

        # compute reprojection error (RMS)
        projected, _ = cv2.projectPoints(object_points, rvec, tvec, self.camera_matrix, self.dist_coeffs)
        projected = projected.reshape(-1, 2)
        diffs = projected - image_points
        reproj_error = np.sqrt((diffs ** 2).sum(axis=1).mean())

        return rvec, tvec, pose_matrix, reproj_error


if __name__ == "__main__":
    from core.services.vision.VisionService import VisionServiceSingleton
    import time
    import threading

    def init_vision_system():
        vision_system = VisionServiceSingleton().get_instance()
        vision_system.contourDetection = False
        vision_system.get_camera_settings().set_brightness_auto(False)

        vision_thread = threading.Thread(target=vision_system.run, daemon=True)
        vision_thread.start()
        return vision_system

    def main():
        vision_system = init_vision_system()

        camera_matrix = vision_system.cameraMatrix
        dst = vision_system.cameraDist  # your distortion coefficients container
        _logger.info("Camera Intrinsics:\n", camera_matrix)

        pose_solver = CameraPoseSolver(PnPConfig(camera_matrix=camera_matrix, dist_coeffs=dst, units="mm"))

        camera_settings = vision_system.get_camera_settings()
        chessboard_size = (camera_settings.get_chessboard_width(), camera_settings.get_chessboard_height())
        square_size_mm = float(camera_settings.get_square_size_mm())
        _logger.info(f"Chessboard size (corners): {chessboard_size}")

        _logger.info(f"Square size (mm): {square_size_mm}")


        pose_computed = False
        while True:
            frame = vision_system.latest_frame
            if frame is None:
                time.sleep(0.01)
                continue

            if pose_computed is False:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # find chessboard corners
                found, corners = cv2.findChessboardCorners(gray, chessboard_size,
                                                           cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)

                if found:
                    # refine
                    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

                    # Create object points in same order as OpenCV returns corners (row-major)
                    width, height = chessboard_size  # width = number of inner corners per row (columns), height = rows
                    objp = np.zeros((width * height, 3), np.float32)
                    # mgrid(y, x) -> (height, width)
                    cols, rows = chessboard_size  # width, height
                    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)

                    # Multiply by square size (units)
                    objp *= square_size_mm  # now in mm. If you prefer meters: objp *= (square_size_mm/1000.0)


                    # Sanity checks
                    if corners.reshape(-1, 2).shape[0] != objp.shape[0]:
                        _logger.warning("WARNING: detected corners count != object points count",

                              corners.shape, objp.shape)
                    else:
                        _logger.info("Detected corners:", corners.reshape(-1, 2)[:6])

                        _logger.info("Object points (first):", objp[:6])


                    # Solve PnP
                    try:
                        rvec, tvec, pose_mat, reproj = pose_solver.solve_pnp(objp, corners.reshape(-1, 2))
                        _logger.error("PnP solved. Reprojection error (px):", reproj)

                        print_pose_explained(pose_mat)
                        pose_computed=True
                    except Exception as e:
                        _logger.error("PnP failed:", e)


                    # draw
                    cv2.drawChessboardCorners(frame, chessboard_size, corners, found)

            cv2.imshow("Camera Frame with Chessboard", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cv2.destroyAllWindows()

    main()
