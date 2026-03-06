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
        try:
            self._pipeline = RefactoredRobotCalibrationPipeline(
                self._config, self._adaptive_config, self._events_config
            )
            success = self._pipeline.run()
        finally:
            self._detach_log_handler(handler)

        self._calibrated = success
        self._status     = "done" if success else "error"
        msg = "Calibration complete" if success else "Calibration failed"
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
