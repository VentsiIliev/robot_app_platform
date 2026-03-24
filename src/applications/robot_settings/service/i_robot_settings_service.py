from abc import ABC, abstractmethod
from typing import Any, Optional, List, Tuple

from src.shared_contracts.declarations import MovementGroupDefinition
from src.engine.robot.configuration import (
    MovementGroup,
    MovementGroupSettings,
    RobotSettings,
    RobotCalibrationSettings,
)


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
    def load_targeting_definitions(self) -> Any: ...

    @abstractmethod
    def save_targeting_definitions(self, targeting: Any) -> None: ...

    @abstractmethod
    def load_movement_groups(self) -> MovementGroupSettings: ...

    @abstractmethod
    def save_movement_groups(self, movement_groups: dict[str, MovementGroup]) -> None: ...

    @abstractmethod
    def get_current_position(self) -> Optional[List[float]]: ...

    @abstractmethod
    def get_slot_info(self) -> List[Tuple[int, Optional[str]]]:
        """Returns (slot_id, tool_name) per slot. tool_name is None if the slot is unassigned."""
        ...

    @abstractmethod
    def get_movement_group_definitions(self) -> List[MovementGroupDefinition]: ...

    @abstractmethod
    def move_to_group(self, group_name: str) -> tuple[bool, str]:
        """Move robot to the named single-position group (PTP). Blocking."""
        ...

    @abstractmethod
    def execute_group(self, group_name: str) -> tuple[bool, str]:
        """Execute the trajectory of the named multi-position group (linear). Blocking."""
        ...

    @abstractmethod
    def move_to_point(self, group_name: str, point_str: str) -> tuple[bool, str]:
        """Move to an explicit point string using the group's vel/acc. Blocking."""
        ...

    @abstractmethod
    def jog(self, axis: str, direction: str, step: float) -> None: ...

    @abstractmethod
    def stop_jog(self) -> None: ...
