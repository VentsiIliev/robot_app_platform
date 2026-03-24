import numpy as np
import os

import logging


class DataManager:
    def __init__(self, storage_path):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.storage_path = storage_path

        if storage_path is None:
            raise ValueError("Storage path cannot be None")

        self.workAreaPoints = None
        self.work_area_polygon = None
        self.pickupAreaPoints = None
        self.sprayAreaPoints = None
        self.namedAreaPoints = {}
        self.cameraToRobotMatrix = None
        self.cameraData = None
        self.perspectiveMatrix = None
        self.isSystemCalibrated = False
        self.build_storage_paths()

    def build_storage_paths(self):
        self._logger.info(f"Building storage paths: {self.storage_path}")
        self.camera_data_path = os.path.join(self.storage_path, 'camera_calibration.npz')
        self.perspective_matrix_path = os.path.join(self.storage_path, 'perspectiveTransform.npy')
        self.camera_to_robot_matrix_path = os.path.join(self.storage_path, 'cameraToRobotMatrix_camera_center.npy')
        self.work_area_points_path = os.path.join(self.storage_path, 'workAreaPoints.npy')
        self.pickup_area_points_path = os.path.join(self.storage_path, 'pickupAreaPoints.npy')
        self.spray_area_points_path = os.path.join(self.storage_path, 'sprayAreaPoints.npy')
        self.named_areas_dir = os.path.join(self.storage_path, "work_areas")
        os.makedirs(self.named_areas_dir, exist_ok=True)

    def loadWorkAreaPoints(self):
        try:
            self.workAreaPoints = np.load(self.work_area_points_path)
            self.work_area_polygon = np.array(self.workAreaPoints, dtype=np.int32).reshape((-1, 1, 2))
            self._logger.info(f"Work area points loaded from: {self.work_area_points_path}")
        except FileNotFoundError:
            self.workAreaPoints = None
            self._logger.error(f"Work area points file not found at {self.work_area_points_path}")

        try:
            self.pickupAreaPoints = np.load(self.pickup_area_points_path)
            self._logger.info(f"Pickup area points loaded from: {self.pickup_area_points_path}")
        except FileNotFoundError:
            self.pickupAreaPoints = None
            self._logger.error(f"Pickup area points file not found at {self.pickup_area_points_path}")

        try:
            self.sprayAreaPoints = np.load(self.spray_area_points_path)
            self._logger.info(f"Spray area points loaded from: {self.spray_area_points_path}")
        except FileNotFoundError:
            self.sprayAreaPoints = None
            self._logger.error(f"Spray area points file not found at {self.spray_area_points_path}")

        self.namedAreaPoints = {}
        for area_name, points in (
            ("work", self.workAreaPoints),
            ("pickup", self.pickupAreaPoints),
            ("spray", self.sprayAreaPoints),
        ):
            if points is not None:
                self.namedAreaPoints[area_name] = points

        for filename in os.listdir(self.named_areas_dir):
            if not filename.endswith(".npy"):
                continue
            area_name = filename[:-4]
            try:
                self.namedAreaPoints[area_name] = np.load(os.path.join(self.named_areas_dir, filename))
                self._logger.info("Named area points loaded for: %s", area_name)
            except Exception as exc:
                self._logger.error("Failed to load named area %s: %s", area_name, exc)

    def loadCameraToRobotMatrix(self):
        try:
            self.cameraToRobotMatrix = np.load(self.camera_to_robot_matrix_path)
            self._logger.info(f"Camera-to-robot matrix loaded from: {self.camera_to_robot_matrix_path}")
        except FileNotFoundError:
            self.cameraToRobotMatrix = None
            self._logger.error(f"Camera-to-robot matrix not found at {self.camera_to_robot_matrix_path}")

    def loadCameraCalibrationData(self):
        try:
            self.cameraData = np.load(self.camera_data_path)
            self.isSystemCalibrated = True
        except FileNotFoundError:
            self.cameraData = None
            self.isSystemCalibrated = False
            self._logger.error(f"Camera calibration data not found at {self.camera_data_path}")

    def loadPerspectiveMatrix(self):
        try:
            self.perspectiveMatrix = np.load(self.perspective_matrix_path)
            self._logger.info(f"Perspective matrix loaded from: {self.perspective_matrix_path}")
        except FileNotFoundError:
            self.perspectiveMatrix = None
            self._logger.info(f"No perspective matrix found at: {self.perspective_matrix_path}")

    def saveWorkAreaPoints(self, data):
        if data is None or len(data) == 0:
            return False, "No data provided to save"

        try:
            if isinstance(data, dict) and 'area_type' in data and 'corners' in data:
                area_type = data['area_type']
                points = data['corners']

                if points is None or len(points) == 0:
                    return False, f"No points provided for {area_type} area"

                points_array = np.array(points, dtype=np.float32)

                if area_type == 'pickup':
                    np.save(self.pickup_area_points_path, points_array)  # ← was work_area_points_path
                    self.pickupAreaPoints = points_array
                    self._logger.info(f"Saved pickup area points to {self.pickup_area_points_path}")
                elif area_type == 'spray':
                    np.save(self.spray_area_points_path, points_array)
                    self.sprayAreaPoints = points_array
                    self._logger.info(f"Saved spray area points to {self.spray_area_points_path}")
                elif area_type == 'work':
                    np.save(self.work_area_points_path, points_array)
                    self.workAreaPoints = points_array
                    self.work_area_polygon = np.array(self.workAreaPoints, dtype=np.int32).reshape((-1, 1, 2))
                    self._logger.info("Saved work area points to %s", self.work_area_points_path)
                else:
                    path = os.path.join(self.named_areas_dir, f"{area_type}.npy")
                    np.save(path, points_array)
                    self._logger.info("Saved named area points to %s", path)
                self.namedAreaPoints[area_type] = points_array
                return True, f"{area_type} area points saved successfully"
            else:
                points_array = np.array(data, dtype=np.float32)
                np.save(self.work_area_points_path, points_array)
                self.workAreaPoints = points_array
                self.work_area_polygon = np.array(self.workAreaPoints, dtype=np.int32).reshape((-1, 1, 2))
                self.namedAreaPoints["work"] = points_array
                self._logger.info("Work area points saved (legacy format)")
                return True, "Work area points saved successfully (legacy format)"

        except Exception as e:
            self._logger.error(f"Error saving work area points: {str(e)}")
            return False, f"Error saving work area points: {str(e)}"

    def get_camera_matrix(self):
        return self.cameraData['mtx'] if self.cameraData is not None else None


    def get_distortion_coefficients(self):
        return self.cameraData['dist'] if self.cameraData is not None else None

    def get_named_area_points(self, area_type: str):
        return self.namedAreaPoints.get(area_type)
