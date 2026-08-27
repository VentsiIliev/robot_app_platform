import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.engine.robot.configuration.robot_settings import MovementGroup
from src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller import (
    PaintProcessSettingsController,
)
from src.robot_systems.paint.applications.paint_process_settings.mapper import PaintProcessSettingsMapper
from src.robot_systems.paint.applications.paint_process_settings.service.paint_process_settings_application_service import (
    PaintProcessSettingsApplicationService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class _FakeModel:
    def __init__(
        self,
        dropoff_configured: bool,
        error: str = "",
        pickup_safety_enabled: tuple[bool, bool] = (True, True),
    ):
        self.current_settings = PaintProcessConfig()
        self._dropoff_configured = dropoff_configured
        self._error = error
        self._pickup_safety_enabled = pickup_safety_enabled
        self.save = MagicMock()
        self.get_current_robot_position = MagicMock(return_value=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    def is_dropoff_movement_group_configured(self) -> bool:
        return self._dropoff_configured

    def dropoff_movement_group_configuration_error(self) -> str:
        return self._error

    def get_pickup_safety_enabled(self) -> tuple[bool, bool]:
        return self._pickup_safety_enabled


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
    def test_selecting_servo_contact_requires_pump_and_sensor(self):
        cases = [
            ((False, False), ("Vacuum Pump in Device Control", "Vacuum Sensor in Device Control")),
            ((False, True), ("Vacuum Pump in Device Control",)),
            ((True, False), ("Vacuum Sensor in Device Control",)),
        ]
        for enabled, expected in cases:
            with self.subTest(enabled=enabled):
                model = _FakeModel(True, pickup_safety_enabled=enabled)
                view = _FakeView()
                view.values_set = {"pickup_contact_mode": "servo_contact"}
                controller = PaintProcessSettingsController(model, view)
                with patch(
                    "src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller.show_warning"
                ) as show_warning:
                    controller._on_value_changed("pickup_contact_mode", "servo_contact")

                show_warning.assert_called_once()
                for missing in expected:
                    self.assertIn(missing, show_warning.call_args.args[2])
                self.assertEqual("planned", view.values_set["pickup_contact_mode"])

    def test_selecting_servo_contact_requires_process_vacuum_pump(self):
        model = _FakeModel(True, pickup_safety_enabled=(True, True))
        view = _FakeView()
        view.values_set = {
            "enable_vacuum_pump": False,
            "pickup_contact_mode": "servo_contact",
        }
        controller = PaintProcessSettingsController(model, view)
        with patch(
            "src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller.show_warning"
        ) as show_warning:
            controller._on_value_changed("pickup_contact_mode", "servo_contact")

        self.assertIn(
            "Enable Vacuum Pump in Paint Process Settings",
            show_warning.call_args.args[2],
        )
        self.assertEqual("planned", view.values_set["pickup_contact_mode"])

    def test_magazine_servo_mode_is_allowed_when_pump_and_sensor_are_enabled(self):
        model = _FakeModel(True, pickup_safety_enabled=(True, True))
        view = _FakeView()
        view.values_set = {"magazine_pickup_mode": "vision_servo_contact"}
        controller = PaintProcessSettingsController(model, view)

        self.assertTrue(controller._servo_contact_is_allowed(view.values_set))

    def test_save_does_not_proceed_with_unsafe_servo_contact(self):
        model = _FakeModel(True, pickup_safety_enabled=(True, False))
        view = _FakeView()
        controller = PaintProcessSettingsController(model, view)
        flat = PaintProcessSettingsMapper.to_flat_dict(model.current_settings)
        flat["pickup_contact_mode"] = "servo_contact"
        with patch(
            "src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller.show_warning"
        ):
            controller._on_save(flat)

        model.save.assert_not_called()
        self.assertEqual("planned", view.values_set["pickup_contact_mode"])

    def test_servo_contact_minimum_z_round_trips(self):
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)
        self.assertEqual(0.0, flat["pickup_servo_contact_min_z_mm"])

        flat["pickup_servo_contact_min_z_mm"] = -5.0
        restored = PaintProcessSettingsMapper.from_flat_dict(flat, base)

        self.assertEqual(-5.0, restored.pickup_motion.servo_contact_min_z_mm)

    def test_motion_profile_tables_round_trip_type_and_blendr(self):
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)
        flat["pickup_motion_profiles"] = [
            {
                "key": "approach",
                "vel_percent": 33,
                "acc_percent": 44,
                "motion_type": "linear",
                "blendR": 12.5,
            }
        ]
        flat["cleanup_motion_profiles"] = [
            {
                "key": "cleanup",
                "vel_percent": 55,
                "acc_percent": 66,
                "motion_type": "ptp",
                "blendR": 7.0,
            }
        ]
        flat["navigation_motion_profiles"] = [
            {
                "key": "calibration_move",
                "vel_percent": 22,
                "acc_percent": 23,
                "motion_type": "linear",
                "blendR": 4.5,
            }
        ]

        mapped = PaintProcessSettingsMapper.from_flat_dict(flat, base)
        round_tripped = PaintProcessSettingsMapper.to_flat_dict(mapped)

        self.assertEqual(mapped.pickup_motion.approach_motion_type, "linear")
        self.assertEqual(mapped.pickup_motion.approach_blendR, 12.5)
        self.assertEqual(mapped.edge_cleanup.motion_type, "ptp")
        self.assertEqual(mapped.edge_cleanup.blendR, 7.0)
        self.assertEqual(mapped.navigation_return.calibration_move_motion_type, "linear")
        self.assertEqual(mapped.navigation_return.calibration_move_blendR, 4.5)
        self.assertEqual(round_tripped["pickup_motion_profiles"][0]["motion_type"], "linear")
        self.assertEqual(round_tripped["navigation_motion_profiles"][0]["blendR"], 4.5)

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
    def test_pickup_safety_reads_persisted_peripheral_enable_flags(self):
        peripherals = SimpleNamespace(
            peripherals={
                "vacuum_pump": SimpleNamespace(enabled=True),
                "vacuum_sensor": SimpleNamespace(enabled=False),
            }
        )
        service = PaintProcessSettingsApplicationService(
            process_config_service=MagicMock(),
            peripherals_provider=lambda: peripherals,
        )

        self.assertEqual((True, False), service.get_pickup_safety_enabled())

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

    def test_move_to_waypoint_dispatches_motion_type_with_robot_tool_and_user(self):
        robot = MagicMock()
        robot.move_linear.return_value = True
        robot.move_ptp.return_value = True
        service = PaintProcessSettingsApplicationService(
            process_config_service=MagicMock(),
            robot_service_provider=lambda: robot,
            robot_tool=3,
            robot_user=4,
        )

        linear = {
            "position": ["1", 2, 3, 4, 5, 6],
            "vel_percent": "70",
            "acc_percent": "30",
            "motion_type": "linear",
            "blendR": "12.5",
        }
        ptp = {
            "position": [7, 8, 9, 10, 11, 12],
            "vel_percent": 50,
            "acc_percent": 20,
            "motion_type": "ptp",
            "blendR": 99,
        }

        self.assertTrue(service.move_to_waypoint(linear))
        self.assertTrue(service.move_to_waypoint(ptp))

        robot.move_linear.assert_called_once_with([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 3, 4, 70.0, 30.0, 12.5, True)
        robot.move_ptp.assert_called_once_with([7.0, 8.0, 9.0, 10.0, 11.0, 12.0], 3, 4, 50.0, 20.0, True)

    def test_move_to_waypoint_uses_live_robot_settings(self):
        robot = MagicMock()
        robot.move_ptp.return_value = True
        robot_config = MagicMock(robot_tool=5, robot_user=6)
        service = PaintProcessSettingsApplicationService(
            process_config_service=MagicMock(),
            robot_service_provider=lambda: robot,
            robot_config_provider=lambda: robot_config,
            robot_tool=1,
            robot_user=2,
        )

        self.assertTrue(service.move_to_waypoint({"position": [1, 2, 3, 4, 5, 6]}))

        robot.move_ptp.assert_called_once_with([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 5, 6, 50.0, 20.0, True)


if __name__ == "__main__":
    unittest.main()
