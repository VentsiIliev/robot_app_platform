import unittest
from unittest.mock import MagicMock, call

from src.engine.robot.services.robot_state_publisher import RobotStatePublisher
from src.engine.robot.services.robot_state_snapshot import RobotStateSnapshot
from src.shared_contracts.events.robot_events import RobotTopics


class TestRobotStatePublisher(unittest.TestCase):

    def setUp(self):
        self.broker = MagicMock()
        self.publisher = RobotStatePublisher(self.broker)
        self.snapshot = RobotStateSnapshot(
            state="moving",
            position=[1.0, 2.0, 3.0, 0.0, 0.0, 0.0],
            velocity=30.0,
            acceleration=20.0,
        )

    def test_publishes_to_state_topic(self):
        self.publisher.publish(self.snapshot)
        self.broker.publish.assert_any_call(RobotTopics.STATE, self.snapshot)

    def test_publishes_position(self):
        self.publisher.publish(self.snapshot)
        self.broker.publish.assert_any_call(RobotTopics.POSITION, self.snapshot.position)

    def test_publishes_velocity(self):
        self.publisher.publish(self.snapshot)
        self.broker.publish.assert_any_call(RobotTopics.VELOCITY, self.snapshot.velocity)

    def test_publishes_acceleration(self):
        self.publisher.publish(self.snapshot)
        self.broker.publish.assert_any_call(RobotTopics.ACCELERATION, self.snapshot.acceleration)

    def test_publishes_exactly_four_topics(self):
        self.publisher.publish(self.snapshot)
        self.assertEqual(self.broker.publish.call_count, 4)

    def test_topic_constants_match(self):
        self.assertEqual(RobotTopics.STATE,        "robot/state")
        self.assertEqual(RobotTopics.POSITION,     "robot/position")
        self.assertEqual(RobotTopics.VELOCITY,     "robot/velocity")
        self.assertEqual(RobotTopics.ACCELERATION, "robot/acceleration")