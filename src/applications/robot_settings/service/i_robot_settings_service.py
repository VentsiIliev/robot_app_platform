from abc import ABC, abstractmethod
from typing import Optional, List, Tuple

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings


class IRobotSettingsService(ABC):

    @abstractmethod
    def load_config(self) -> RobotSettings: ...

    @abstractmethod
    def save_config(self, config: RobotSettings) -> None: ...

    @abstractmethod
    def load_calibration(self) -> RobotCalibrationSettings: ...

    @abstractmethod
    def save_calibration(self, calibration: RobotCalibrationSettings) -> None: ...

    @abstractmethod
    def get_current_position(self) -> Optional[List[float]]: ...

    @abstractmethod
    def get_slot_info(self) -> List[Tuple[int, Optional[str]]]:
        """Returns (slot_id, tool_name) per slot. tool_name is None if the slot is unassigned."""
        ...

    @abstractmethod
    def move_to_group(self, group_name: str) -> bool:
        """Move robot to the named single-position group (PTP). Blocking."""
        ...

    @abstractmethod
    def execute_group(self, group_name: str) -> bool:
        """Execute the trajectory of the named multi-position group (linear). Blocking."""
        ...

    @abstractmethod
    def move_to_point(self, group_name: str, point_str: str) -> bool:
        """Move to an explicit point string using the group's vel/acc. Blocking."""
        ...
