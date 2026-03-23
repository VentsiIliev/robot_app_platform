from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from src.robot_systems.base_robot_system import BaseRobotSystem


class RobotSystemBootstrapProvider(ABC):
    """Robot-system-owned bootstrap composition for startup-only concerns."""

    @property
    @abstractmethod
    def system_class(self) -> Type[BaseRobotSystem]:
        ...

    @abstractmethod
    def build_robot(self):
        ...

    @abstractmethod
    def build_login_view(self, robot_system: BaseRobotSystem, messaging_service):
        ...

    @abstractmethod
    def build_authorization_service(self, robot_system: BaseRobotSystem):
        ...
