import logging
from src.engine.vision.implementation.VisionSystem.core.data_loading import DataManager
from src.engine.vision.implementation.VisionSystem.core.service.interfaces.i_service import IService
from src.engine.vision.implementation.VisionSystem.core.settings.CameraSettings import CameraSettings
from src.engine.vision.implementation.VisionSystem.core.settings.settings_manager import SettingsManager
from src.engine.vision.implementation.VisionSystem.core.path_resolver import get_user_config_path
class Service(IService):
    def __init__(self, data_storage_path, settings_file_path: str = None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.data_manager = DataManager(data_storage_path)
        config_path = settings_file_path or str(get_user_config_path())
        self.settings_manager = SettingsManager(config_file_path=config_path)
    # ---------------- Settings interface ----------------
    def loadSettings(self):
        settings = self.settings_manager.loadSettings()
        self._logger.info(f"[SettingsManager] settings type in loadSettings")

        self._logger.info(type(settings))

        default_settings = CameraSettings()
        CameraSettings.from_dict(default_settings, settings)
        settings = default_settings
        self._logger.info(f"[SettingsManager] after from dict {type(settings)} {settings}")

        return settings
    def updateSettings(self, camera_settings, settings: dict,
                       brightness_controller=None, reinit_camera=None) -> tuple[bool, str]:
        return self.settings_manager.updateSettings(
            camera_settings, settings,
            brightness_controller=brightness_controller,
            reinit_camera=reinit_camera,
        )
    def saveSettings(self, settings: dict) -> None:
        self.settings_manager.saveSettings(settings)
    # ---------------- DataManager interface ----------------
    def loadPerspectiveMatrix(self):
        self.data_manager.loadPerspectiveMatrix()
    def loadCameraCalibrationData(self):
        self.data_manager.loadCameraCalibrationData()
    def loadCameraToRobotMatrix(self):
        self.data_manager.loadCameraToRobotMatrix()
    def loadWorkAreaPoints(self):
        self.data_manager.loadWorkAreaPoints()
    def saveWorkAreaPoints(self, data):
        return self.data_manager.saveWorkAreaPoints(data)
    # ---------------- Convenience properties ----------------
    @property
    def cameraData(self):
        return self.data_manager.cameraData
    @property
    def camera_to_robot_matrix_path(self):
        return self.data_manager.camera_to_robot_matrix_path
    @property
    def cameraToRobotMatrix(self):
        return self.data_manager.cameraToRobotMatrix
    @cameraToRobotMatrix.setter
    def cameraToRobotMatrix(self, value):
        self.data_manager.cameraToRobotMatrix = value
        self._logger.info("cameraToRobotMatrix updated in Service")
    @property
    def perspectiveMatrix(self):
        return self.data_manager.perspectiveMatrix

    @perspectiveMatrix.setter
    def perspectiveMatrix(self, value):
        self.data_manager.perspectiveMatrix = value
        self._logger.info("perspectiveMatrix updated in Service")
    @property
    def sprayAreaPoints(self):
        return self.data_manager.sprayAreaPoints
    @property
    def pickupAreaPoints(self):
        return self.data_manager.pickupAreaPoints
    @property
    def workAreaPoints(self):
        return self.data_manager.workAreaPoints
    def get_camera_matrix(self):
        return self.data_manager.get_camera_matrix()
    def get_distortion_coefficients(self):
        return self.data_manager.get_distortion_coefficients()
    @property
    def isCalibrated(self) -> bool:
        return (
            self.data_manager.cameraData is not None and
            self.data_manager.cameraToRobotMatrix is not None
        )
