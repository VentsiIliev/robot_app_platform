from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IChoreographySetupService(ABC):
    @abstractmethod
    def list_choreographies(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def load_choreography(self, choreography_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def new_choreography(self, choreography_id: str, name: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def save_choreography(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    def capture_robot(self, robot_name: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def robot_state(self, robot_name: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def jog(self, robot_name: str, command: str, axis: str, direction: str, step: float) -> int:
        ...

    @abstractmethod
    def stop_servo_jog(self, robot_name: str) -> int:
        ...

    @abstractmethod
    def joint_jog(self, robot_name: str, command: str, joint: str, direction: str, step: float) -> int:
        ...
