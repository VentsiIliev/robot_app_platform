from __future__ import annotations

import logging
import time

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.robot.interfaces.i_robot_service import IRobotService

_logger = logging.getLogger(__name__)


class VacuumPumpController(IVacuumPumpController):
    ON_VALUE = True
    OFF_VALUE = False

    def __init__(
        self,
        robot_service: IRobotService,
        digital_output: int = 1,
        reset_output: int = 2,
        reset_pulse_s: float = 0.3,
    ) -> None:
        self._robot = robot_service
        self.digital_output = int(digital_output)
        self.reset_output = int(reset_output)
        self.reset_pulse_s = float(reset_pulse_s)

    def turn_on(self) -> bool:
        ok = self._robot.set_digital_output(self.digital_output, self.ON_VALUE)
        if ok:
            _logger.info("Vacuum pump ON (do=%s)", self.digital_output)
        else:
            _logger.warning("Vacuum pump ON failed (do=%s)", self.digital_output)
        return ok

    def turn_off(self) -> bool:
        ok = self._robot.set_digital_output(self.digital_output, self.OFF_VALUE)
        if not ok:
            _logger.warning("Vacuum pump OFF failed (do=%s)", self.digital_output)
            return False

        reset_high = self._robot.set_digital_output(self.reset_output, True)
        time.sleep(self.reset_pulse_s)
        reset_low = self._robot.set_digital_output(self.reset_output, False)
        success = bool(reset_high and reset_low)
        if success:
            _logger.info(
                "Vacuum pump OFF (do=%s reset_do=%s pulse=%.3fs)",
                self.digital_output,
                self.reset_output,
                self.reset_pulse_s,
            )
        else:
            _logger.warning("Vacuum pump reset pulse failed (reset_do=%s)", self.reset_output)
        return success
