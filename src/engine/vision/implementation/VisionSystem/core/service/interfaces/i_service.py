from abc import ABC, abstractmethod
from typing import Tuple, Any


class IService(ABC):
    # ...existing code...

    @abstractmethod
    def updateSettings(self,
                       camera_settings,
                       settings: dict,
                       brightness_controller=None,
                       reinit_camera=None) -> Tuple[bool, str]:
        pass

    # ---------------- Calibration / DataManager methods ----------------
    @abstractmethod
    def loadPerspectiveMatrix(self):
        """Load perspective matrix from storage"""
        pass

    @abstractmethod
    def loadCameraCalibrationData(self):
        """Load camera calibration data"""
        pass

    @abstractmethod
    def loadCameraToRobotMatrix(self):
        """Load camera-to-robot homography"""
        pass

    @abstractmethod
    def loadWorkAreaPoints(self):
        """Load pickup, spray, and work area points"""
        pass

    @abstractmethod
    def saveWorkAreaPoints(self, data: Any) -> Tuple[bool, str]:
        """Save work area points"""
        pass

    # ---------------- Convenience properties ----------------
    @property
    @abstractmethod
    def cameraData(self):
        pass

    @property
    @abstractmethod
    def cameraToRobotMatrix(self):
        pass

    @cameraToRobotMatrix.setter
    @abstractmethod
    def cameraToRobotMatrix(self, value):
        pass

    @property
    @abstractmethod
    def perspectiveMatrix(self):
        pass

    @property
    @abstractmethod
    def camera_to_robot_matrix_path(self):
        pass

    @property
    @abstractmethod
    def sprayAreaPoints(self):
        pass

    @abstractmethod
    def get_camera_matrix(self):
        pass

    @abstractmethod
    def get_distortion_coefficients(self):
        pass

    @property
    @abstractmethod
    def isCalibrated(self) -> bool:
        """True if the vision_service has both camera calibration data and camera-to-robot matrix."""
        pass