import unittest
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.config import (
    MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP,
    MAGAZINE_PICKUP_TARGET_MODE_VISION,
    PICKUP_CONTACT_MODE_SERVO_CONTACT,
    PaintMagazineLoadConfig,
    PaintProcessConfig,
    PickupMotionConfig,
)
from src.robot_systems.paint.processes.paint.execution_control import PaintExecutionControl
from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_execute_pickup_release_handler import (
    _verify_fixed_pickup_start_pose,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_move_to_magazine_handler import (
    handle_magazine_move_to_magazine,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_prepare_pickup_release_handler import (
    handle_magazine_prepare_pickup_release,
)
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState
from src.robot_systems.paint.processes.paint.paint_process_config_serializer import (
    PaintProcessConfigSerializer,
)
from src.robot_systems.paint.applications.paint_process_settings.mapper import (
    PaintProcessSettingsMapper,
)


class TestFixedMagazinePickup(unittest.TestCase):
    def test_old_settings_default_to_vision_targeting(self):
        restored = PaintProcessConfigSerializer().from_dict({"magazine_load": {"enabled": True}})

        self.assertEqual(MAGAZINE_PICKUP_TARGET_MODE_VISION, restored.magazine_load.pickup_target_mode)

    def test_fixed_group_settings_round_trip_through_ui_mapper(self):
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)
        flat.update({
            "magazine_pickup_target_mode": MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP,
            "magazine_fixed_pickup_group_id": "Magazine Pickup Taught",
            "magazine_fixed_pickup_position_tolerance_mm": 1.5,
            "magazine_fixed_pickup_orientation_tolerance_deg": 0.75,
        })

        restored = PaintProcessSettingsMapper.from_flat_dict(flat, base)

        self.assertEqual(MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP, restored.magazine_load.pickup_target_mode)
        self.assertEqual("Magazine Pickup Taught", restored.magazine_load.fixed_pickup_group_id)
        self.assertEqual(1.5, restored.magazine_load.fixed_pickup_position_tolerance_mm)
        self.assertEqual(0.75, restored.magazine_load.fixed_pickup_orientation_tolerance_deg)

    def test_fixed_mode_moves_to_fixed_group_and_skips_camera_wait(self):
        load_service = MagicMock()
        load_service._move_to_group_with_pause_resume_recovery.return_value = True
        service = MagicMock()
        service._magazine_load_service = load_service
        config = PaintMagazineLoadConfig(
            enabled=True,
            pickup_target_mode=MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP,
            fixed_pickup_group_id="Magazine Fixed Pickup",
        )
        ctx = self._context(service, config)

        next_state = handle_magazine_move_to_magazine(ctx)

        self.assertEqual(PaintExecutionState.MAGAZINE_PREPARE_PICKUP_RELEASE, next_state)
        self.assertEqual("Magazine Fixed Pickup", ctx.magazine_group)
        self.assertEqual(
            "Magazine Fixed Pickup",
            load_service._move_to_group_with_pause_resume_recovery.call_args.args[2],
        )

    def test_fixed_prepare_does_not_use_snapshot_or_vision_target_resolver(self):
        fixed_pose = [10.0, 20.0, 100.0, 179.0, 0.0, -179.0]
        calibration_pose = [30.0, 40.0, 200.0, 180.0, 0.0, 0.0]
        load_service = MagicMock()
        load_service._navigation.get_group_position.side_effect = [fixed_pose, calibration_pose]
        load_service._validated_pose.return_value = fixed_pose
        service = MagicMock()
        service._magazine_load_service = load_service
        config = PaintMagazineLoadConfig(
            enabled=True,
            pickup_target_mode=MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP,
            release_z_mm=50.0,
        )
        process_config = PaintProcessConfig(
            magazine_load=config,
            pickup_motion=PickupMotionConfig(
                magazine_pickup_contact_mode=PICKUP_CONTACT_MODE_SERVO_CONTACT
            ),
        )
        ctx = self._context(service, config, process_config=process_config)
        ctx.magazine_group = "Magazine Fixed Pickup"
        ctx.calibration_group = "CALIBRATION"

        next_state = handle_magazine_prepare_pickup_release(ctx)

        self.assertEqual(PaintExecutionState.MAGAZINE_EXECUTE_PICKUP_RELEASE, next_state)
        self.assertEqual(fixed_pose, ctx.magazine_fixed_pickup_pose)
        self.assertEqual([30.0, 40.0, 50.0, 180.0, 0.0, 0.0], ctx.magazine_release_pose)
        load_service._resolve_pickup_target.assert_not_called()
        load_service._resolve_work_area_center_release_pose.assert_not_called()

    def test_fixed_prepare_rejects_non_servo_contact_mode(self):
        load_service = MagicMock()
        load_service._navigation.get_group_position.side_effect = [
            [0.0, 0.0, 100.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 200.0, 0.0, 0.0, 0.0],
        ]
        service = MagicMock()
        service._magazine_load_service = load_service
        config = PaintMagazineLoadConfig(
            enabled=True,
            pickup_target_mode=MAGAZINE_PICKUP_TARGET_MODE_FIXED_GROUP,
        )
        ctx = self._context(service, config, process_config=PaintProcessConfig(magazine_load=config))
        ctx.magazine_group = "Magazine Fixed Pickup"
        ctx.calibration_group = "CALIBRATION"

        next_state = handle_magazine_prepare_pickup_release(ctx)

        self.assertEqual(PaintExecutionState.ERROR, next_state)
        self.assertIn("requires servo_contact", ctx.result_message)

    def test_start_pose_verification_accepts_wrapped_angles(self):
        robot = MagicMock()
        robot.get_current_position_fresh.return_value = [0.5, 0.0, 100.0, -179.0, 0.0, 179.0]

        ok, message = _verify_fixed_pickup_start_pose(
            robot,
            [0.0, 0.0, 100.0, 179.0, 0.0, -179.0],
            position_tolerance_mm=1.0,
            orientation_tolerance_deg=2.1,
        )

        self.assertTrue(ok, message)

    def test_start_pose_verification_refuses_position_mismatch(self):
        robot = MagicMock()
        robot.get_current_position_fresh.return_value = [3.0, 0.0, 100.0, 0.0, 0.0, 0.0]

        ok, message = _verify_fixed_pickup_start_pose(
            robot,
            [0.0, 0.0, 100.0, 0.0, 0.0, 0.0],
            position_tolerance_mm=2.0,
            orientation_tolerance_deg=1.0,
        )

        self.assertFalse(ok)
        self.assertIn("position error 3.000 mm", message)

    @staticmethod
    def _context(service, config, *, process_config=None):
        return PaintExecutionContext(
            production_service=service,
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            process_config=process_config or PaintProcessConfig(magazine_load=config),
            magazine_config=config,
        )


if __name__ == "__main__":
    unittest.main()
