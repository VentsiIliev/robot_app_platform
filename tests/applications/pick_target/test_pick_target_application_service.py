import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.applications.pick_target.service.pick_target_application_service import (
    PickTargetApplicationService,
)


class TestPickTargetApplicationService(unittest.TestCase):
    def test_transform_point_uses_live_resolver_getter(self):
        registry = MagicMock()
        target_point = object()
        registry.by_name.return_value = target_point
        resolver = MagicMock()
        resolver.registry = registry
        resolver.resolve.return_value = SimpleNamespace(final_xy=(123.0, 456.0))
        pickup_frame = SimpleNamespace(mapper=SimpleNamespace(target_pose=SimpleNamespace(rz=90.0)))
        resolver.get_frame.return_value = pickup_frame

        service = PickTargetApplicationService(
            vision_service=None,
            capture_snapshot_service=None,
            robot_service=None,
            resolver=None,
            resolver_getter=lambda: resolver,
            robot_config=None,
            navigation=None,
            default_target_name="tool",
            calibration_frame_name="calibration",
            pickup_frame_name="pickup",
        )

        result = service._transform_point(10.0, 20.0)

        self.assertEqual((123.0, 456.0), result)
        registry.by_name.assert_called_with("tool")
        self.assertEqual("calibration", resolver.resolve.call_args.kwargs["frame"])

    def test_set_target_uses_current_resolver_registry(self):
        registry = MagicMock()
        first_target = object()
        second_target = object()
        registry.by_name.side_effect = [first_target, second_target]
        resolver = MagicMock()
        resolver.registry = registry
        resolver.get_frame.return_value = None

        service = PickTargetApplicationService(
            vision_service=None,
            capture_snapshot_service=None,
            robot_service=None,
            resolver=None,
            resolver_getter=lambda: resolver,
            robot_config=None,
            navigation=None,
            default_target_name="tool",
            calibration_frame_name="calibration",
            pickup_frame_name="pickup",
        )

        self.assertIs(service._target_point, first_target)
        service.set_target("camera")

        self.assertIs(service._target_point, second_target)
        self.assertEqual(registry.by_name.call_args_list[-1].args[0], "camera")

    def test_transform_point_uses_active_frame_name_getter(self):
        registry = MagicMock()
        resolver = MagicMock()
        resolver.registry = registry
        resolver.resolve.return_value = SimpleNamespace(final_xy=(11.0, 22.0))

        service = PickTargetApplicationService(
            vision_service=None,
            capture_snapshot_service=None,
            robot_service=None,
            resolver=None,
            resolver_getter=lambda: resolver,
            robot_config=None,
            navigation=None,
            default_target_name="tool",
            calibration_frame_name="calibration",
            pickup_frame_name="",
            active_frame_name_getter=lambda: "magazine",
        )

        self.assertEqual((11.0, 22.0), service._transform_point(1.0, 2.0))
        self.assertEqual("magazine", resolver.resolve.call_args.kwargs["frame"])

    def test_jog_reference_uses_active_frame_mapper(self):
        registry = MagicMock()
        resolver = MagicMock()
        resolver.registry = registry
        resolver.get_frame.return_value = SimpleNamespace(
            mapper=SimpleNamespace(target_pose=SimpleNamespace(rz=37.5))
        )

        service = PickTargetApplicationService(
            vision_service=None,
            capture_snapshot_service=None,
            robot_service=None,
            resolver=None,
            resolver_getter=lambda: resolver,
            robot_config=None,
            navigation=None,
            default_target_name="tool",
            calibration_frame_name="calibration",
            pickup_frame_name="",
            active_frame_name_getter=lambda: "magazine",
        )

        self.assertEqual(37.5, service.get_jog_reference_rz())
        resolver.get_frame.assert_called_once_with("magazine")

    def test_move_to_calibration_position_routes_to_active_capture_group(self):
        navigation = MagicMock()
        service = PickTargetApplicationService(
            vision_service=None,
            capture_snapshot_service=None,
            robot_service=None,
            resolver=None,
            resolver_getter=None,
            robot_config=None,
            navigation=navigation,
            default_target_name="tool",
            calibration_frame_name="calibration",
            pickup_frame_name="",
            active_capture_group_getter=lambda: "Magazine",
        )

        navigation.move_to_group.return_value = True

        self.assertTrue(service.move_to_calibration_position())
        navigation.move_to_group.assert_called_once_with("Magazine")
        navigation.move_to_calibration_position.assert_not_called()


if __name__ == "__main__":
    unittest.main()
