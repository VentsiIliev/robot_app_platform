from src.robot_systems.glue.component_ids import ProcessID
from src.engine.robot.calibration.robot_calibration_process import RobotCalibrationProcess as _Base
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.robot.calibration.i_robot_calibration_service import IRobotCalibrationService
from src.engine.system.i_system_manager import ISystemManager
from src.engine.process.process_requirements import ProcessRequirements
from typing import Callable, Optional


class RobotCalibrationProcess(_Base):
    """Thin subclass that pins the process_id to glue's ProcessID.ROBOT_CALIBRATION."""

    def __init__(
        self,
        calibration_service: IRobotCalibrationService,
        messaging:           IMessagingService,
        system_manager:      Optional[ISystemManager]        = None,
        requirements:        Optional[ProcessRequirements]   = None,
        service_checker:     Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(
            calibration_service = calibration_service,
            messaging           = messaging,
            process_id          = ProcessID.ROBOT_CALIBRATION,
            system_manager      = system_manager,
            requirements        = requirements,
            service_checker     = service_checker,
        )