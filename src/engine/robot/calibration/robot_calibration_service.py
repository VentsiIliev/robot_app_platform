import logging
from src.engine.robot.calibration.i_robot_calibration_service import IRobotCalibrationService
from src.engine.robot.calibration.robot_calibration.robot_calibration_pipeline import RefactoredRobotCalibrationPipeline
from src.engine.robot.calibration.robot_calibration.config_helpers import (
    RobotCalibrationConfig,
    AdaptiveMovementConfig,
    RobotCalibrationEventsConfig,
)

_logger = logging.getLogger(__name__)
_CALIBRATION_ROOT = "src.engine.robot.calibration"


class _BrokerLogHandler(logging.Handler):
    def __init__(self, broker, topic):
        super().__init__()
        self._broker = broker
        self._topic  = topic
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        try:
            self._broker.publish(self._topic, self.format(record))
        except Exception:
            pass


class RobotCalibrationService(IRobotCalibrationService):

    def __init__(
        self,
        config: RobotCalibrationConfig,
        adaptive_config: AdaptiveMovementConfig = None,
        events_config: RobotCalibrationEventsConfig = None,
    ):
        self._config         = config
        self._adaptive_config = adaptive_config
        self._events_config  = events_config
        self._calibrated     = False
        self._status         = "idle"
        self._pipeline       = None

    def run_calibration(self) -> tuple[bool, str]:
        self._status  = "running"
        handler       = self._attach_log_handler()
        auto_brightness_locked = False
        auto_brightness_adjustment_locked = False
        vision_service = getattr(self._config, "vision_service", None)
        try:
            if (
                vision_service is not None
                and vision_service.get_auto_brightness_enabled()
            ):
                auto_brightness_locked = vision_service.lock_auto_brightness_region()
                if auto_brightness_locked:
                    _logger.info("Locking auto brightness region during robot calibration")
                else:
                    _logger.warning("Unable to lock auto brightness region during robot calibration")
                vision_service.lock_auto_brightness_adjustment()
                auto_brightness_adjustment_locked = True
                _logger.info("Freezing auto brightness adjustment during robot calibration")
            self._refresh_runtime_settings()
            self._pipeline = RefactoredRobotCalibrationPipeline(
                self._config, self._adaptive_config, self._events_config
            )
            success, msg = self._pipeline.run()
        finally:
            if vision_service is not None and auto_brightness_adjustment_locked:
                _logger.info("Restoring adaptive auto brightness adjustment after robot calibration")
                vision_service.unlock_auto_brightness_adjustment()
            if vision_service is not None and auto_brightness_locked:
                _logger.info("Restoring dynamic auto brightness region after robot calibration")
                vision_service.unlock_auto_brightness_region()
            self._detach_log_handler(handler)

        self._calibrated = success
        if self._status != "stopped":
            self._status = "done" if success else "error"
        _logger.info(msg)
        return success, msg

    def stop_calibration(self) -> None:
        if self._pipeline:
            self._pipeline.calibration_state_machine.stop_execution()
            self._status = "stopped"
        try:
            self._config.robot_service.stop_motion()
        except Exception:
            pass

    def is_calibrated(self) -> bool:
        return self._calibrated

    def get_status(self) -> str:
        return self._status

    def _attach_log_handler(self):
        if not self._events_config:
            return None
        handler = _BrokerLogHandler(
            self._events_config.broker,
            self._events_config.calibration_log_topic,
        )
        logging.getLogger(_CALIBRATION_ROOT).addHandler(handler)
        return handler

    def _detach_log_handler(self, handler) -> None:
        if handler is None:
            return
        logging.getLogger(_CALIBRATION_ROOT).removeHandler(handler)
        handler.close()

    def _refresh_runtime_settings(self) -> None:
        settings = getattr(self._config, "settings_service", None)
        if settings is None:
            return

        calibration_key = getattr(self._config, "calibration_settings_key", None)
        if calibration_key is not None:
            live_calibration = settings.get(calibration_key)
            if live_calibration is not None:
                self._config.required_ids = live_calibration.required_ids
                self._config.z_target = live_calibration.z_target
                self._config.velocity = live_calibration.velocity
                self._config.acceleration = live_calibration.acceleration
                self._config.run_height_measurement = live_calibration.run_height_measurement
                self._config.camera_tcp_offset_config = live_calibration.camera_tcp_offset
                self._config.axis_mapping_config = live_calibration.axis_mapping
                self._adaptive_config = live_calibration.adaptive_movement

        robot_config_key = getattr(self._config, "robot_config_key", None)
        if robot_config_key is not None:
            live_robot_config = settings.get(robot_config_key)
            if live_robot_config is not None:
                self._config.robot_config = live_robot_config
                self._config.robot_tool = live_robot_config.robot_tool
                self._config.robot_user = live_robot_config.robot_user
