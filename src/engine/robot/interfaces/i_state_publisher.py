from abc import ABC, abstractmethod
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot


class IStatePublisher(ABC):

    @abstractmethod
    def publish(self, snapshot: RobotStateSnapshot) -> None:
        ...
