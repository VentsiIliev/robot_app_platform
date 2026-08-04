import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.configuration.robot_settings import MovementGroup
from src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller import (
    PaintProcessSettingsController,
)
from src.robot_systems.paint.applications.paint_process_settings.service.paint_process_settings_application_service import (
    PaintProcessSettingsApplicationService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class _FakeModel:
    def __init__(self, dropoff_configured: bool, error: str = ""):
        self.current_settings = PaintProcessConfig()
        self._dropoff_configured = dropoff_configured
        self._error = error
        self.save = MagicMock()
        self.get_current_robot_position = MagicMock(return_value=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    def is_dropoff_movement_group_configured(self) -> bool:
        return self._dropoff_configured

    def dropoff_movement_group_configuration_error(self) -> str:
        return self._error


class _FakeView:
    def __init__(self):
        self.values_set = None
        self.status = ""

    def set_values(self, values: dict) -> None:
        self.values_set = dict(values)

    def values(self) -> dict:
        return dict(self.values_set or {})

    def set_status(self, message: str) -> None:
        self.status = message

    def set_safe_travel_position(self, position: list[float]) -> None:
        self.values_set = {"safe_travel_position": ", ".join(f"{value:.3f}" for value in position)}

    def set_dropoff_safe_travel_position(self, position: list[float]) -> None:
        self.values_set = {"dropoff_safe_travel_position": ", ".join(f"{value:.3f}" for value in position)}


class TestPaintProcessSettingsController(unittest.TestCase):
    def test_save_rejects_movement_group_strategy_when_dropoff_group_is_not_configured(self):
        model = _FakeModel(
            dropoff_configured=False,
            error="Dropoff movement group velocity must be greater than 0.",
        )
        view = _FakeView()
        controller = PaintProcessSettingsController(model, view)

        with patch(
            "src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller.show_warning"
        ) as show_warning:
            controller._on_save({"dropoff_strategy": "movement_group"})

        model.save.assert_not_called()
        show_warning.assert_called_once()
        self.assertIn("velocity must be greater than 0", show_warning.call_args.args[2])
        self.assertEqual("pickup_origin", view.values_set["dropoff_strategy"])
        self.assertIn("velocity must be greater than 0", view.status)

    def test_set_safe_travel_current_captures_current_robot_pose_into_view(self):
        model = _FakeModel(dropoff_configured=True)
        view = _FakeView()
        controller = PaintProcessSettingsController(model, view)

        controller._on_set_safe_travel_current()

        model.get_current_robot_position.assert_called_once_with()
        self.assertEqual({"safe_travel_position": "1.000, 2.000, 3.000, 4.000, 5.000, 6.000"}, view.values_set)
        self.assertIn("Safe travel pose set", view.status)

    def test_set_dropoff_safe_travel_current_captures_current_robot_pose_into_view(self):
        model = _FakeModel(dropoff_configured=True)
        view = _FakeView()
        controller = PaintProcessSettingsController(model, view)

        controller._on_set_dropoff_safe_travel_current()

        model.get_current_robot_position.assert_called_once_with()
        self.assertEqual({"dropoff_safe_travel_position": "1.000, 2.000, 3.000, 4.000, 5.000, 6.000"}, view.values_set)
        self.assertIn("Paint-to-dropoff safe travel pose set", view.status)

    def test_save_rejects_enabled_safe_travel_without_captured_pose(self):
        model = _FakeModel(dropoff_configured=True)
        view = _FakeView()
        controller = PaintProcessSettingsController(model, view)

        with patch(
            "src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller.show_warning"
        ) as show_warning:
            controller._on_save({"safe_travel_enabled": True, "safe_travel_position": ""})

        model.save.assert_not_called()
        show_warning.assert_called_once()
        self.assertFalse(view.values_set["safe_travel_enabled"])
        self.assertIn("Safe travel pose is not set", view.status)

    def test_save_rejects_enabled_dropoff_safe_travel_without_captured_pose(self):
        model = _FakeModel(dropoff_configured=True)
        view = _FakeView()
        controller = PaintProcessSettingsController(model, view)

        with patch(
            "src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller.show_warning"
        ) as show_warning:
            controller._on_save({"dropoff_safe_travel_enabled": True, "dropoff_safe_travel_position": ""})

        model.save.assert_not_called()
        show_warning.assert_called_once()
        self.assertFalse(view.values_set["dropoff_safe_travel_enabled"])
        self.assertIn("Paint-to-dropoff safe travel pose is not set", view.status)


class TestPaintProcessSettingsApplicationService(unittest.TestCase):
    def test_dropoff_group_validation_requires_position_velocity_and_acceleration(self):
        process_config_service = MagicMock()
        cases = [
            (MovementGroup(velocity=10, acceleration=10), "Dropoff movement group position is missing."),
            (
                MovementGroup(velocity=0, acceleration=10, position="[1, 2, 3, 4, 5, 6]"),
                "Dropoff movement group velocity must be greater than 0 in Robot Settings.",
            ),
            (
                MovementGroup(velocity=10, acceleration=0, position="[1, 2, 3, 4, 5, 6]"),
                "Dropoff movement group acceleration must be greater than 0 in Robot Settings.",
            ),
            (MovementGroup(velocity=10, acceleration=10, position="[1, 2, 3, 4, 5, 6]"), ""),
        ]
        for group, expected_error in cases:
            with self.subTest(group=group):
                service = PaintProcessSettingsApplicationService(
                    process_config_service=process_config_service,
                    dropoff_group_provider=lambda group=group: group,
                )

                self.assertEqual(expected_error, service.dropoff_movement_group_configuration_error())
                self.assertEqual(expected_error == "", service.is_dropoff_movement_group_configured())

    def test_current_robot_position_is_read_from_provider_and_normalized(self):
        service = PaintProcessSettingsApplicationService(
            process_config_service=MagicMock(),
            current_position_provider=lambda: ["1", 2, 3, 4, 5, 6],
        )

        self.assertEqual([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], service.get_current_robot_position())


if __name__ == "__main__":
    unittest.main()
