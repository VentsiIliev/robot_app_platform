import logging
from src.engine.core.message_broker import MessageBroker
from src.engine.robot.interfaces.i_state_publisher import IStatePublisher
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot
from src.shared_contracts.events.robot_events import RobotTopics


class RobotStatePublisher(IStatePublisher):

    def __init__(self, broker: MessageBroker):
        self._broker = broker
        self._logger = logging.getLogger(self.__class__.__name__)

    def publish(self, snapshot: RobotStateSnapshot) -> None:
        self._logger.debug("Publishing robot state snapshot: %s", snapshot)
        self._broker.publish(RobotTopics.STATE,        snapshot)
        self._broker.publish(RobotTopics.POSITION,     snapshot.position)
        self._broker.publish(RobotTopics.VELOCITY,     snapshot.velocity)
        self._broker.publish(RobotTopics.ACCELERATION, snapshot.acceleration)
