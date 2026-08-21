import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.engine.robot.procedures import TimedDummyPickupCondition, VacuumPickupCondition
from src.robot_systems.paint.component_ids import ServiceID
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem


class TestPaintPickupConditionWiring(unittest.TestCase):
    @staticmethod
    def _system(*, dummy_enabled: bool, sensor):
        system = PaintRobotSystem.__new__(PaintRobotSystem)
        system._paint_process_config_service = MagicMock()
        system._paint_process_config_service.get_snapshot.return_value = SimpleNamespace(
            pickup_motion=SimpleNamespace(
                servo_contact_dummy_sensor_enabled=dummy_enabled,
                servo_contact_dummy_detect_after_s=0.25,
            )
        )
        system.get_optional_service = MagicMock(return_value=sensor)
        return system

    def test_real_vacuum_sensor_is_used_as_stop_condition(self) -> None:
        sensor = MagicMock()
        system = self._system(dummy_enabled=False, sensor=sensor)

        condition = system._build_pickup_condition()

        self.assertIsInstance(condition, VacuumPickupCondition)
        self.assertIs(condition._vacuum_sensor, sensor)
        system.get_optional_service.assert_called_once_with(ServiceID.VACUUM_SENSOR)

    def test_dummy_condition_remains_explicit_override(self) -> None:
        system = self._system(dummy_enabled=True, sensor=MagicMock())

        condition = system._build_pickup_condition()

        self.assertIsInstance(condition, TimedDummyPickupCondition)
        system.get_optional_service.assert_not_called()

    def test_missing_sensor_leaves_condition_unconfigured(self) -> None:
        system = self._system(dummy_enabled=False, sensor=None)

        self.assertIsNone(system._build_pickup_condition())


if __name__ == "__main__":
    unittest.main()
