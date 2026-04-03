import logging
import os

from dataclasses import dataclass
from typing import Optional, List
import cv2
import numpy as np

import cv2.aruco as aruco

from src.engine.vision.implementation.plvision.PLVision.Calibration import CameraCalibrator

_logger = logging.getLogger(__name__)

@dataclass
class CameraCalibrationServiceResult:
    """
    Result class for camera calibration operations.
    
    Contains all the data returned from a calibration operation including
    success status, calibration matrices, and diagnostic information.
    """
    success: bool
    message: str
    camera_matrix: Optional[np.ndarray] = None
    distortion_coefficients: Optional[np.ndarray] = None
    perspective_matrix: Optional[np.ndarray] = None
    rotation_vectors: Optional[List[np.ndarray]] = None
    translation_vectors: Optional[List[np.ndarray]] = None
    valid_images_count: int = 0
    calibration_error: Optional[float] = None
    storage_path: Optional[str] = None
    
    @property
    def calibration_data(self) -> Optional[List[np.ndarray]]:
        """
        Legacy format: [distortion_coefficients, camera_matrix]
        For backward compatibility with existing code.
        """
        if self.success and self.distortion_coefficients is not None and self.camera_matrix is not None:
            return [self.distortion_coefficients, self.camera_matrix]
        return None
    
    @property
    def is_calibrated(self) -> bool:
        """Check if calibration was successful and has valid data."""
        return (self.success and 
                self.camera_matrix is not None and 
                self.distortion_coefficients is not None)
    
    def to_legacy_tuple(self) -> tuple:
        """
        Convert to legacy tuple format for backward compatibility.
        Returns: (success, calibration_data, perspective_matrix, message)
        """
        return (self.success, self.calibration_data, self.perspective_matrix, self.message)


class CameraCalibrationService:
    # Default storage path: folder next to this module under 'storage/calibration_result'
    DEFAULT_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'calibration_result')

    def __init__(self, chessboardWidth,
                 chessboardHeight,
                 squareSizeMM,
                 skipFrames,
                 message_publisher,
                 storagePath,
                 onDetectionFailed=None,
                 messaging_service=None):
        # Determine storage path priority:
        # 1. Explicitly passed storagePath
        # 3. Default global path
        if storagePath is None:
            raise ValueError("Storage path cannot be None")
        self.STORAGE_PATH = storagePath
        _logger.info(f"📁 CameraCalibrationService: Using storage path: {self.STORAGE_PATH}")


        # Ensure storage directory exists
        if not os.path.exists(self.STORAGE_PATH):
            os.makedirs(self.STORAGE_PATH, exist_ok=True)
            _logger.info(f"📁 Created calibration storage directory: {self.STORAGE_PATH}")


        self.calibrationImages = []
        self.chessboardWidth = chessboardWidth
        self.chessboardHeight = chessboardHeight
        self.squareSizeMM = squareSizeMM
        self.skipFrames = skipFrames
        self.message_publisher = message_publisher
        self.onDetectionFailed = onDetectionFailed
        self.cameraCalibrator = CameraCalibrator(self.chessboardWidth, self.chessboardHeight, self.squareSizeMM)

        self.messaging_service = messaging_service
    
    @property
    def PERSPECTIVE_MATRIX_PATH(self):
        """Dynamic path to a perspective transform matrix file"""
        return os.path.join(self.STORAGE_PATH, 'perspectiveTransform.npy')
    
    @property 
    def CAMERA_TO_ROBOT_MATRIX_PATH(self):
        """Dynamic path to camera-to-robot matrix file"""
        return os.path.join(self.STORAGE_PATH, 'cameraToRobotMatrix.npy')

    def detectArucoMarkers(self, flip=False, image=None):
        """
        Detects ArUco markers in the provided image.
        Returns corners, ids, and the (possibly flipped) image.
        """
        if image is None:
            _logger.info("No image provided for ArUco detection.")

            return None, None, None

        if flip:
            image = cv2.flip(image, 1)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_250)
        parameters = aruco.DetectorParameters()
        detector = aruco.ArucoDetector(dictionary, parameters)

        try:
            corners, ids, _ = detector.detectMarkers(gray)
            if ids is not None:
                _logger.info(f"✅ Detected ArUco IDs: {ids.flatten()}")

            else:
                _logger.error("❌ No ArUco markers detected")

            return corners, ids, image
        except Exception as e:
            _logger.error(f"❌ ArUco Detection failed: {e}")

            return None, None, image

    def detectPerspectiveCorrectionMarkers(self, image):
        """
        Detect ArUco markers (IDs 30, 31, 32, 33) for perspective correction.
        Returns corners in order: top-left (30), top-right (31), bottom-right (32), bottom-left (33)
        """
        required_marker_ids = [30, 31, 32, 33]  # top-left, top-right, bottom-right, bottom-left
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_250)
        parameters = aruco.DetectorParameters()
        detector = aruco.ArucoDetector(dictionary, parameters)
        
        try:
            corners, ids, _ = detector.detectMarkers(gray)
            if ids is None:
                return False, None, "No ArUco markers detected for perspective correction"
            
            # Create a mapping of marker ID to corners
            marker_corners = {}
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id in required_marker_ids:
                    # Get the top-left corner of each marker
                    marker_corners[marker_id] = corners[i][0][0]  # top-left corner
            
            # Check if all required markers are found
            missing_markers = [mid for mid in required_marker_ids if mid not in marker_corners]
            if missing_markers:
                return False, None, f"Missing perspective correction markers: {missing_markers}"
            
            # Order corners: top-left (30), top-right (31), bottom-right (32), bottom-left (33)
            ordered_corners = [
                marker_corners[30],  # top-left
                marker_corners[31],  # top-right
                marker_corners[32],  # bottom-right
                marker_corners[33]   # bottom-left
            ]
            
            return True, ordered_corners, "Perspective correction markers detected successfully"
            
        except Exception as e:
            return False, None, f"Error detecting perspective correction markers: {str(e)}"
    

    def _validate_calibration_result(self, camera_matrix, dist_coeffs, image_size, rms):
        """Return a list of human-readable rejection reasons, or [] if the result looks sane."""
        width, height = image_size
        fx = float(camera_matrix[0, 0])
        fy = float(camera_matrix[1, 1])
        cx = float(camera_matrix[0, 2])
        cy = float(camera_matrix[1, 2])
        d = dist_coeffs.ravel()
        k2 = float(d[1]) if len(d) > 1 else 0.0
        k3 = float(d[4]) if len(d) > 4 else 0.0
        hfov = np.degrees(2.0 * np.arctan2(width / 2.0, fx))
        vfov = np.degrees(2.0 * np.arctan2(height / 2.0, fy))

        errors = []
        if not np.isfinite(rms):
            errors.append("RMS is not finite")
        if fx <= 0 or fy <= 0:
            errors.append(f"Non-positive focal length fx={fx:.2f} fy={fy:.2f}")
        if abs(cx - width / 2) > 0.2 * width:
            errors.append(f"cx too far from center: {cx:.2f} (expected ~{width/2:.0f})")
        if abs(cy - height / 2) > 0.2 * height:
            errors.append(f"cy too far from center: {cy:.2f} (expected ~{height/2:.0f})")
        if abs(k2) > 10:
            errors.append(f"k2 suspiciously large: {k2:.3f}")
        if abs(k3) > 50:
            errors.append(f"k3 suspiciously large: {k3:.3f}")
        if hfov < 15 or vfov < 10:
            errors.append(f"FOV suspiciously narrow: HFOV={hfov:.2f}° VFOV={vfov:.2f}°")
        return errors

    def computePerspectiveCorrection(self, image, src_corners, output_size=(1280, 720)):
        """
        Compute perspective transformation matrix and apply correction.
        """
        # Define destination rectangle (rectified image)
        dst_corners = np.array([
            [0, 0],                           # top-left
            [output_size[0] - 1, 0],         # top-right
            [output_size[0] - 1, output_size[1] - 1],  # bottom-right
            [0, output_size[1] - 1]          # bottom-left
        ], dtype=np.float32)
        
        src_corners = np.array(src_corners, dtype=np.float32)
        
        # Compute perspective transformation matrix
        perspective_matrix = cv2.getPerspectiveTransform(src_corners, dst_corners)
        
        # Apply perspective correction
        corrected_image = cv2.warpPerspective(image, perspective_matrix, output_size)
        
        return corrected_image, perspective_matrix

    def cleanupOldCalibrationFiles(self):
        """
        Delete old calibration files to ensure fresh calibration.
        """
        files_to_delete = [
            os.path.join(self.STORAGE_PATH, 'perspectiveTransform.npy'),
            os.path.join(self.STORAGE_PATH, 'calibration_data.npz'),
            os.path.join(self.STORAGE_PATH, 'camera_calibration.npz')
        ]
        
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    _logger.info(f"🗑️ Deleted old calibration file: {os.path.basename(file_path)}")

            except Exception as e:
                _logger.warning(f"⚠️ Could not delete {file_path}: {e}")

    def _compute_perspective_from_chessboard(self, corners_refined):
        cols, rows = self.chessboardWidth, self.chessboardHeight
        tl = corners_refined[0, 0]
        tr = corners_refined[cols - 1, 0]
        br = corners_refined[(rows - 1) * cols + (cols - 1), 0]
        bl = corners_refined[(rows - 1) * cols, 0]

        src = np.array([tl, tr, br, bl], dtype=np.float32)
        cx, cy = src.mean(axis=0)

        phys_w = (cols - 1) * self.squareSizeMM
        phys_h = (rows - 1) * self.squareSizeMM

        h_span = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2.0
        v_span = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2.0
        avg_ppm = ((h_span / phys_w) + (v_span / phys_h)) / 2.0

        dst_w = phys_w * avg_ppm
        dst_h = phys_h * avg_ppm
        dst = np.array([
            [cx - dst_w / 2, cy - dst_h / 2],
            [cx + dst_w / 2, cy - dst_h / 2],
            [cx + dst_w / 2, cy + dst_h / 2],
            [cx - dst_w / 2, cy + dst_h / 2],
        ], dtype=np.float32)

        matrix = cv2.getPerspectiveTransform(src, dst)
        _logger.info("Perspective matrix derived from chessboard outer corners "
                      "(tl=%s, tr=%s, br=%s, bl=%s)", tl, tr, br, bl)

        tilt_x_rad = np.arctan2(matrix[0, 1], matrix[0, 0])
        tilt_y_rad = np.arctan2(-matrix[1, 0], matrix[1, 1])
        rx_deg = np.degrees(tilt_y_rad)
        ry_deg = -np.degrees(tilt_x_rad)
        _logger.info(
            "📐 Camera tilt from chessboard perspective matrix:\n"
            "  ┌─────────────────────────────────────────┐\n"
            "  │  Axis │    rad    │    deg    │ Workobj  │\n"
            "  ├─────────────────────────────────────────┤\n"
            "  │  RX   │  %+.4f  │  %+.3f°  │  %+.3f°  │\n"
            "  │  RY   │  %+.4f  │  %+.3f°  │  %+.3f°  │\n"
            "  │  RZ   │   0.0000  │   0.000°  │   0.000° │\n"
            "  └─────────────────────────────────────────┘",
            tilt_y_rad, rx_deg, -rx_deg,
            -tilt_x_rad, ry_deg, -ry_deg,
        )

        return matrix

    def run(self, image, debug=True) -> CameraCalibrationServiceResult:
        """
        Main calibration workflow with perspective correction support.
        Returns CameraCalibrationServiceResult containing all calibration data.
        """
        message = ""
        
        # Clean up old calibration files at the start
        self.cleanupOldCalibrationFiles()

        if not self.calibrationImages or len(self.calibrationImages) <= 0:
            message = "No calibration images provided"
            self.publish(message)
            _logger.info(message)

            return CameraCalibrationServiceResult(
                success=False,
                message=message
            )
        
        # Track if perspective correction was applied
        perspective_matrix_for_vision = None
        
        # If we have only one image, try perspective correction with ArUco markers
        if len(self.calibrationImages) == 1:
            _logger.info("Single image detected - attempting perspective correction with ArUco markers")

            single_image = self.calibrationImages[0]
            
            # Detect perspective correction markers
            success, corners, detect_message = self.detectPerspectiveCorrectionMarkers(single_image)
            if success:
                _logger.info(f"✅ {detect_message}")

                self.publish(detect_message)
                
                # Apply perspective correction
                corrected_image, perspective_matrix_for_vision = self.computePerspectiveCorrection(single_image, corners)
                
                # Save the corrected image for debugging
                corrected_path = os.path.join(self.STORAGE_PATH, 'perspective_corrected.png')
                cv2.imwrite(corrected_path, corrected_image)
                _logger.info(f"📸 Perspective corrected image saved to: {corrected_path}")

                
                # Test chessboard detection on corrected image before proceeding
                gray_corrected = cv2.cvtColor(corrected_image, cv2.COLOR_BGR2GRAY)
                chessboard_size = (self.chessboardWidth, self.chessboardHeight)
                ret_test, corners_test = cv2.findChessboardCorners(gray_corrected, chessboard_size, None)
                
                if ret_test:
                    _logger.info(f"✅ Chessboard detected in perspective-corrected image: {len(corners_test)} corners")

                else:
                    _logger.warning(f"⚠️ Chessboard NOT detected in perspective-corrected image")

                    _logger.info(f"   Expected chessboard size: {chessboard_size[0]}x{chessboard_size[1]} = {chessboard_size[0] * chessboard_size[1]} corners")

                    _logger.info(f"   Trying different detection flags...")

                    
                    # Try with different flags
                    flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FILTER_QUADS
                    ret_test, corners_test = cv2.findChessboardCorners(gray_corrected, chessboard_size, flags)
                    
                    if ret_test:
                        _logger.info(f"✅ Chessboard detected with alternative flags: {len(corners_test)} corners")

                    else:
                        _logger.error(f"❌ Chessboard still not detected - check image quality and chessboard size")

                        _logger.info(f"   Image size after correction: {corrected_image.shape[1]}x{corrected_image.shape[0]}")

                
                # Replace the original image with the corrected one
                self.calibrationImages = [corrected_image]
                
                message = "Perspective correction applied successfully"
                self.publish(message)
            else:
                _logger.error(f"❌ {detect_message}")

                self.publish(detect_message)
                _logger.info("Proceeding with calibration without perspective correction")


        # Prepare object points
        chessboard_size = (self.chessboardWidth, self.chessboardHeight)
        square_size = self.squareSizeMM
        objp = np.zeros((np.prod(chessboard_size), 3), np.float32)
        objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
        objp *= square_size

        objpoints = []  # 3d points in real world space
        imgpoints = []  # 2d points in image plane

        message = f"Processing {len(self.calibrationImages)} images for chessboard detection..."
        self.publish(message)
        _logger.info(message)


        valid_images = 0
        detection_flags = (
            cv2.CALIB_CB_ADAPTIVE_THRESH
            | cv2.CALIB_CB_NORMALIZE_IMAGE
            | cv2.CALIB_CB_FILTER_QUADS
        )
        for idx, img in enumerate(self.calibrationImages):
            if img is None:
                continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Find the chessboard corners (robust flags first, fall back to default)
            ret, corners = cv2.findChessboardCorners(gray, chessboard_size, detection_flags)
            if not ret:
                ret, corners = cv2.findChessboardCorners(gray, chessboard_size, None)

            if ret:
                objpoints.append(objp)

                # Refine corner positions
                corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                            criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
                imgpoints.append(corners2)

                # Log board coverage diagnostics
                pts = corners2.reshape(-1, 2)
                min_xy = pts.min(axis=0)
                max_xy = pts.max(axis=0)
                center_xy = pts.mean(axis=0)
                bbox_w = max_xy[0] - min_xy[0]
                bbox_h = max_xy[1] - min_xy[1]
                _logger.info(
                    "Image %d: board center=(%.1f, %.1f) bbox=(%.1f x %.1f px)",
                    idx, center_xy[0], center_xy[1], bbox_w, bbox_h,
                )

                # Draw onto a copy so calibration images are not mutated
                vis = img.copy()
                cv2.drawChessboardCorners(vis, chessboard_size, corners2, ret)
                output_path = os.path.join(self.STORAGE_PATH, f'calib_result_{idx:03d}.png')
                cv2.imwrite(output_path, vis)

                valid_images += 1
                _logger.info(f"✅ Chessboard detected in image {idx}")

                message = f"✅ Chessboard detected in image {idx} - saved to {output_path}"
                self.publish(message)
            else:
                _logger.error(f"❌ No chessboard found in image {idx}")

                message = f"❌ No chessboard found in image {idx}"
                self.publish(message)

        if valid_images < 1:  # Need at least 1 good images for calibration
            message = f"Insufficient valid images for calibration. Found {valid_images}, need at least 1."
            _logger.error(f"❌ {message}")

            self.publish(message)
            return CameraCalibrationServiceResult(
                success=False,
                message=message
            )

        # Perform camera calibration
        _logger.info(f"🔧 Performing calibration with {valid_images} valid images...")

        # print images resolution
        for image in self.calibrationImages:
            _logger.info(f"   Image resolution: {image.shape[1]}x{image.shape[0]}")

        message = f"🔧 Performing calibration with {valid_images} valid images..."
        self.publish(message)

        try:
            # print the objpoints and imgpoints sizes and shapes
            _logger.info(f"Object points count: {len(objpoints)} shape: {objpoints[0].shape if objpoints else 'N/A'}")

            _logger.info(f"Image points count: {len(imgpoints)} shape: {imgpoints[0].shape if imgpoints else 'N/A'}")

            self.imgpoints = imgpoints  # Store for coverage visualization
            if imgpoints:
                self.visualize_corner_coverage(img_shape=gray.shape)

            # Seed with a physically plausible intrinsic matrix so the solver
            # starts near a sane solution and is less likely to overfit weak data.
            h, w = gray.shape[:2]
            initial_camera_matrix = np.array([
                [w, 0, w / 2.0],
                [0, w, h / 2.0],
                [0, 0, 1],
            ], dtype=np.float64)
            initial_dist_coeffs = np.zeros((5, 1), dtype=np.float64)

            # FIX_K3: prevents high-order radial term from absorbing pose ambiguity.
            # CALIB_USE_INTRINSIC_GUESS: let the seeded matrix guide the optimiser.
            calib_flags = cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_FIX_K3

            rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
                objpoints, imgpoints, gray.shape[::-1],
                initial_camera_matrix, initial_dist_coeffs,
                flags=calib_flags,
            )

            # rms is the RMS reprojection error — not a boolean.
            if not np.isfinite(rms):
                raise ValueError(f"Calibration RMS is not finite: {rms}")

            validation_errors = self._validate_calibration_result(
                camera_matrix, dist_coeffs, gray.shape[::-1], rms
            )
            if validation_errors:
                message = "Calibration rejected: " + "; ".join(validation_errors)
                _logger.error("❌ %s", message)
                self.publish(message)
                return CameraCalibrationServiceResult(success=False, message=message)

            fx = camera_matrix[0, 0]
            fy = camera_matrix[1, 1]
            cx = camera_matrix[0, 2]
            cy = camera_matrix[1, 2]
            _logger.info(f"Calibration RMS: {rms:.6f}")
            _logger.info(f"Camera Matrix:\n{camera_matrix}")
            _logger.info(f"Distortion Coefficients:\n{dist_coeffs.ravel()}")
            _logger.info(f"Camera calibrated: fx = {fx:.2f}, fy = {fy:.2f}, cx = {cx:.2f}, cy = {cy:.2f}")

            # Save calibration results in both formats for compatibility
            calibration_file = os.path.join(self.STORAGE_PATH, 'calibration_data.npz')
            np.savez(calibration_file,
                     camera_matrix=camera_matrix,
                     dist_coeffs=dist_coeffs,
                     rvecs=rvecs,
                     tvecs=tvecs)

            # Also save in the old format for VisionSystem compatibility
            old_calibration_file = os.path.join(self.STORAGE_PATH, 'camera_calibration.npz')
            np.savez(old_calibration_file,
                     mtx=camera_matrix,
                     dist=dist_coeffs)

            # Compute perspective matrix from chessboard if not already set by ArUco path
            if perspective_matrix_for_vision is None and imgpoints:
                perspective_matrix_for_vision = self._compute_perspective_from_chessboard(imgpoints[0])

            # Save perspective matrix if available
            if perspective_matrix_for_vision is not None:
                perspective_file = os.path.join(self.STORAGE_PATH, 'perspectiveTransform.npy')
                np.save(perspective_file, perspective_matrix_for_vision)
                _logger.info(f"🔄 Perspective transformation matrix saved to: {perspective_file}")
                self.publish("Perspective transformation matrix saved")

            # Store in instance variables
            self.camera_matrix = camera_matrix
            self.dist_coeffs = dist_coeffs
            self.calibrated = True

            _logger.info("✅ Camera calibration completed successfully!")
            _logger.info(f"📊 Calibration parameters saved to: {calibration_file}")
            _logger.info(f"📊 Legacy format saved to: {old_calibration_file}")

            message = f"Calibration successful with {valid_images} images"
            self.publish(f"✅ Camera calibration completed successfully!")
            self.publish(f"📊 Calibration parameters saved successfully")
            self.publish(message)

            self._log_calibration_report(
                camera_matrix, dist_coeffs,
                objpoints, imgpoints, rvecs, tvecs,
                gray.shape[::-1],  # (width, height)
            )

            return CameraCalibrationServiceResult(
                success=True,
                message=message,
                camera_matrix=camera_matrix,
                distortion_coefficients=dist_coeffs,
                perspective_matrix=perspective_matrix_for_vision,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            message = f"Exception during calibration: {str(e)}"
            self.publish(message)
            return CameraCalibrationServiceResult(
                success=False,
                message=message
            )

    def publish(self,message):
        if self.message_publisher is None:
            return
        self.message_publisher.publish_calibration_feedback(message)

    def compute_total_reprojection_error(self, objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist_coeffs):
        """
        Compute the total mean reprojection error for all calibration images.

        Parameters:
            objpoints    : list of np.ndarray, 3D object points in world coordinates
            imgpoints    : list of np.ndarray, 2D image points detected
            rvecs        : list of np.ndarray, rotation vectors from calibration
            tvecs        : list of np.ndarray, translation vectors from calibration
            camera_matrix: np.ndarray, intrinsic camera matrix
            dist_coeffs  : np.ndarray, distortion coefficients

        Returns:
            mean_error   : float, average reprojection error in pixels
        """
        total_error = 0
        total_points = 0

        for i in range(len(objpoints)):
            # Project 3D points to image plane
            projected_imgpoints, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], camera_matrix, dist_coeffs)
            # Compute L2 distance between detected and projected points
            error = cv2.norm(imgpoints[i], projected_imgpoints, cv2.NORM_L2)
            total_error += error ** 2
            total_points += len(objpoints[i])

        mean_error = np.sqrt(total_error / total_points)
        _logger.info(f"📊 Total mean reprojection error: {mean_error:.4f} pixels")

        return mean_error

    def visualize_reprojection(self, objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist_coeffs):
        """
        Visualize reprojection of 3D points onto calibration images.

        objpoints: list of 3D object points
        imgpoints: list of detected 2D image points
        rvecs, tvecs: rotation and translation vectors from calibrateCamera
        camera_matrix, dist_coeffs: calibration parameters
        """
        for i, (objp, imgp, rvec, tvec) in enumerate(zip(objpoints, imgpoints, rvecs, tvecs)):
            # Project the 3D points back into the image
            projected_points, _ = cv2.projectPoints(objp, rvec, tvec, camera_matrix, dist_coeffs)
            projected_points = projected_points.reshape(-1, 2)

            # Convert original image to color if grayscale
            img = self.calibrationImages[i].copy()
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            # Draw detected corners in green
            for pt in imgp:
                pt = pt.ravel()
                cv2.circle(img, (int(pt[0]), int(pt[1])), 5, (0, 255, 0), -1)

            # Draw reprojected points in red
            for pt in projected_points:
                cv2.circle(img, (int(pt[0]), int(pt[1])), 3, (0, 0, 255), -1)

            output_path = os.path.join(self.STORAGE_PATH, f'reprojection_{i:03d}.png')
            cv2.imwrite(output_path, img)
            _logger.info(f"📸 Reprojection visualization saved: {output_path}")


    def _log_calibration_report(
        self,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        objpoints: list,
        imgpoints: list,
        rvecs: list,
        tvecs: list,
        image_size: tuple,  # (width, height)
    ) -> None:
        """
        Log a comprehensive calibration report: camera matrix, distortion coefficients,
        FOV, pose coverage (extrinsics summary), and per-image reprojection errors + extrinsics.
        """
        width, height = image_size
        fx = camera_matrix[0, 0]
        fy = camera_matrix[1, 1]
        cx = camera_matrix[0, 2]
        cy = camera_matrix[1, 2]
        skew = camera_matrix[0, 1]
        aspect = fx / fy if fy != 0 else float("nan")

        hfov = np.degrees(2.0 * np.arctan2(width / 2.0, fx))
        vfov = np.degrees(2.0 * np.arctan2(height / 2.0, fy))

        d = dist_coeffs.ravel()
        dist_labels = ["k1", "k2", "p1", "p2", "k3", "k4", "k5", "k6"]
        dist_parts = "  ".join(
            f"{dist_labels[i]}={d[i]:+.6f}" for i in range(len(d))
        )

        # ── Extrinsic summary ─────────────────────────────────────────────────
        txs = [float(t.ravel()[0]) for t in tvecs]
        tys = [float(t.ravel()[1]) for t in tvecs]
        tzs = [float(t.ravel()[2]) for t in tvecs]
        rot_mags = [float(np.linalg.norm(r)) * 180.0 / np.pi for r in rvecs]

        tx_min, tx_max = min(txs), max(txs)
        ty_min, ty_max = min(tys), max(tys)
        tz_min, tz_max = min(tzs), max(tzs)
        rot_min, rot_max = min(rot_mags), max(rot_mags)

        _logger.info(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║              CAMERA CALIBRATION REPORT                      ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  INTRINSIC MATRIX                                            ║\n"
            "║    fx  = %10.4f px      fy  = %10.4f px            ║\n"
            "║    cx  = %10.4f px      cy  = %10.4f px            ║\n"
            "║    skew= %10.6f         fx/fy ratio = %.6f          ║\n"
            "║    image size: %d × %d px                                ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  DISTORTION COEFFICIENTS                                     ║\n"
            "║    %s\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  FIELD OF VIEW                                               ║\n"
            "║    H-FOV = %.2f °       V-FOV = %.2f °                  ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  POSE COVERAGE  (board → camera, %d images)                ║\n"
            "║    tx  [%+8.2f … %+8.2f] mm                             ║\n"
            "║    ty  [%+8.2f … %+8.2f] mm                             ║\n"
            "║    tz  [%+8.2f … %+8.2f] mm  (depth range)              ║\n"
            "║    tilt [%6.2f … %6.2f] °   (rotation magnitude)        ║\n"
            "╚══════════════════════════════════════════════════════════════╝",
            fx, fy, cx, cy, skew, aspect, width, height,
            dist_parts, hfov, vfov,
            len(rvecs),
            tx_min, tx_max, ty_min, ty_max, tz_min, tz_max, rot_min, rot_max,
        )

        # ── Per-image reprojection errors ─────────────────────────────────────
        per_image_errors = []
        per_image_max = []
        for i, (objp, imgp, rvec, tvec) in enumerate(zip(objpoints, imgpoints, rvecs, tvecs)):
            projected, _ = cv2.projectPoints(objp, rvec, tvec, camera_matrix, dist_coeffs)
            diff = imgp.reshape(-1, 2) - projected.reshape(-1, 2)
            errs = np.linalg.norm(diff, axis=1)
            per_image_errors.append(float(errs.mean()))
            per_image_max.append(float(errs.max()))

        overall_mean = float(np.mean(per_image_errors))
        overall_max = float(np.max(per_image_max))
        overall_min = float(np.min(per_image_errors))
        overall_std = float(np.std(per_image_errors))

        best_idx = int(np.argmin(per_image_errors))
        worst_idx = int(np.argmax(per_image_errors))

        lines = ["\n  PER-IMAGE REPROJECTION ERRORS"]
        lines.append(f"  {'Img':>4}  {'Mean (px)':>10}  {'Max (px)':>10}")
        lines.append(f"  {'---':>4}  {'---------':>10}  {'--------':>10}")
        for i, (mean_e, max_e) in enumerate(zip(per_image_errors, per_image_max)):
            marker = " ◄ worst" if i == worst_idx else (" ◄ best" if i == best_idx else "")
            lines.append(f"  {i:>4}  {mean_e:>10.4f}  {max_e:>10.4f}{marker}")
        lines.append("")
        lines.append(f"  SUMMARY  mean={overall_mean:.4f} px  max={overall_max:.4f} px  "
                     f"min={overall_min:.4f} px  std={overall_std:.4f} px")
        _logger.info("\n".join(lines))

        # ── Per-image extrinsics ───────────────────────────────────────────────
        ext_lines = ["\n  PER-IMAGE EXTRINSICS  (board→camera)"]
        ext_lines.append(
            f"  {'Img':>4}  {'tx (mm)':>9}  {'ty (mm)':>9}  {'tz (mm)':>9}  {'tilt (°)':>9}"
        )
        ext_lines.append(
            f"  {'---':>4}  {'-------':>9}  {'-------':>9}  {'-------':>9}  {'--------':>9}"
        )
        for i, (rvec, tvec) in enumerate(zip(rvecs, tvecs)):
            t = tvec.ravel()
            rot_deg = float(np.linalg.norm(rvec)) * 180.0 / np.pi
            ext_lines.append(
                f"  {i:>4}  {t[0]:>+9.2f}  {t[1]:>+9.2f}  {t[2]:>+9.2f}  {rot_deg:>9.2f}"
            )
        _logger.info("\n".join(ext_lines))

        # ── Publish summary to UI ─────────────────────────────────────────────
        summary = (
            f"[Calibration Report] mean_err={overall_mean:.4f}px  max_err={overall_max:.4f}px  "
            f"fx={fx:.1f} fy={fy:.1f} cx={cx:.1f} cy={cy:.1f}  "
            f"HFOV={hfov:.1f}° VFOV={vfov:.1f}°  "
            f"tz=[{tz_min:.1f}…{tz_max:.1f}]mm  tilt=[{rot_min:.1f}…{rot_max:.1f}]°"
        )
        self.publish(summary)

    def visualize_corner_coverage(self, img_shape=None, point_size=3):
        """
        Draw all detected chessboard corners from all calibration images
        onto a single black-and-white canvas to visualize coverage.

        img_shape: tuple (height, width), optional. Defaults to first image shape.
        point_size: int, radius of circles to draw
        """
        if not self.calibrationImages or not hasattr(self, 'imgpoints') or not self.imgpoints:
            _logger.error("❌ No detected points available for coverage visualization")

            return

        # Determine canvas size
        if img_shape is None:
            img_shape = self.calibrationImages[0].shape[:2]  # (height, width)

        canvas = np.zeros((img_shape[0], img_shape[1]), dtype=np.uint8)

        # Draw all points
        for imgp in self.imgpoints:
            for pt in imgp:
                x, y = int(pt[0][0]), int(pt[0][1])
                cv2.circle(canvas, (x, y), point_size, 255, -1)  # white points

        # Save or show
        coverage_path = os.path.join(self.STORAGE_PATH, 'corner_coverage.png')
        cv2.imwrite(coverage_path, canvas)
        _logger.info(f"📊 Corner coverage visualization saved: {coverage_path}")


        return canvas
