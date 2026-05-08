import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.targeting import TargetFrameDefinition
from src.shared_contracts.declarations import WorkAreaDefinition
from src.robot_systems.paint.calibration.provider import PaintRobotSystemCalibrationProvider
from src.robot_systems.paint.navigation import PaintNavigationService
from src.robot_systems.paint.targeting.frames import build_paint_target_frames
from src.robot_systems.paint.targeting.provider import PaintRobotSystemTargetingProvider
from src.robot_systems.paint.targeting.registry import build_paint_point_registry


class TestPaintNavigationService(unittest.TestCase):
    def test_move_home_uses_capture_offset_and_sets_pickup_area(self):
        navigation = MagicMock()
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = 12.5
        work_area_service = MagicMock()
        group = MagicMock()
        group.parse_position.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        navigation._get_group.return_value = group
        navigation.move_to_position.return_value = True
        service = PaintNavigationService(
            navigation,
            vision=vision,
            work_area_service=work_area_service,
        )

        ok = service.move_home()

        self.assertTrue(ok)
        navigation.move_to_position.assert_called_once_with(
            [1.0, 2.0, 15.5, 4.0, 5.0, 6.0],
            "HOME",
            wait_cancelled=None,
        )
        work_area_service.set_active_area_id.assert_called_once_with("pickup")

    def test_move_to_group_sets_observed_area_only_on_success(self):
        navigation = MagicMock()
        work_area_service = MagicMock()
        service = PaintNavigationService(
            navigation,
            work_area_service=work_area_service,
            observed_area_by_group={"CALIBRATION": "paint"},
        )
        navigation.move_to_group.return_value = True

        self.assertTrue(service.move_to_group("CALIBRATION"))
        work_area_service.set_active_area_id.assert_called_once_with("paint")

        work_area_service.reset_mock()
        navigation.move_to_group.return_value = False
        self.assertFalse(service.move_to_group("CALIBRATION"))
        work_area_service.set_active_area_id.assert_not_called()

    def test_get_group_position_returns_none_on_lookup_or_parse_failure(self):
        navigation = MagicMock()
        service = PaintNavigationService(navigation)

        navigation._get_group.side_effect = RuntimeError("boom")
        self.assertIsNone(service.get_group_position("A"))

        group = MagicMock()
        group.parse_position.side_effect = RuntimeError("bad parse")
        navigation._get_group.side_effect = None
        navigation._get_group.return_value = group
        self.assertIsNone(service.get_group_position("A"))

    def test_move_with_z_offset_returns_false_when_group_has_no_position(self):
        navigation = MagicMock()
        group = MagicMock()
        group.parse_position.return_value = None
        navigation._get_group.return_value = group
        service = PaintNavigationService(navigation)

        self.assertFalse(service._move_with_z_offset("HOME", 5.0))
        navigation.move_to_position.assert_not_called()

    def test_simple_navigation_methods_delegate_and_set_observed_area_on_success(self):
        navigation = MagicMock()
        work_area_service = MagicMock()
        service = PaintNavigationService(
            navigation,
            work_area_service=work_area_service,
            observed_area_by_group={" PAINT ": " spray "},
        )
        navigation.move_to_group.return_value = True
        navigation.move_linear_group.return_value = True
        navigation.move_to_position.return_value = True

        self.assertTrue(service.move_to_login_position())
        self.assertTrue(service.move_to("PAINT"))
        self.assertTrue(service.move_linear("PAINT"))
        self.assertTrue(service.move_linear_group("PAINT"))
        self.assertTrue(service.move_to_position([1, 2, 3], "PAINT"))

        navigation.move_to_group.assert_any_call("LOGIN")
        navigation.move_to_group.assert_any_call("PAINT", wait_cancelled=None)
        navigation.move_linear_group.assert_any_call("PAINT")
        navigation.move_to_position.assert_any_call([1, 2, 3], "PAINT", wait_cancelled=None)
        self.assertEqual(work_area_service.set_active_area_id.call_count, 4)
        work_area_service.set_active_area_id.assert_called_with("spray")

    def test_move_to_uses_z_offset_path_and_get_group_names_delegates(self):
        navigation = MagicMock()
        navigation.get_group_names.return_value = ["A", "B"]
        group = MagicMock()
        group.parse_position.return_value = [1.0, 2.0, 3.0]
        navigation._get_group.return_value = group
        navigation.move_to_position.return_value = True
        service = PaintNavigationService(navigation)

        self.assertTrue(service.move_to("A", z_offset=2.5))
        self.assertEqual(service.get_group_names(), ["A", "B"])
        navigation.move_to_position.assert_called_once_with([1.0, 2.0, 5.5], "A", wait_cancelled=None)

    def test_set_area_falls_back_to_vision_when_work_area_service_missing(self):
        navigation = MagicMock()
        vision = MagicMock()
        service = PaintNavigationService(navigation, vision=vision)

        service._set_area("paint")

        vision.set_active_work_area.assert_called_once_with("paint")


class TestPaintCalibrationProvider(unittest.TestCase):
    def test_build_calibration_navigation_rejects_undefined_paint_area(self):
        work_area_service = MagicMock()
        navigation = MagicMock()
        robot_system = MagicMock()
        robot_system.get_work_area_definitions.return_value = [
            WorkAreaDefinition(id="paint", label="Paint", color="#FF8C32")
        ]
        robot_system.get_service.side_effect = lambda service_id: {
            CommonServiceID.WORK_AREAS: work_area_service,
            CommonServiceID.NAVIGATION: navigation,
        }[service_id]
        provider = PaintRobotSystemCalibrationProvider(robot_system)

        with self.assertRaisesRegex(ValueError, "Calibration area 'spray' is not declared"):
            provider.build_calibration_navigation()

        work_area_service.set_active_area_id.assert_not_called()
        navigation.move_to_group.assert_not_called()

    def test_build_calibration_navigation_sets_area_when_declared(self):
        work_area_service = MagicMock()
        navigation = MagicMock()
        robot_system = MagicMock()
        robot_system.get_work_area_definitions.return_value = [
            WorkAreaDefinition(id="spray", label="Spray", color="#FF8C32")
        ]
        robot_system.get_service.side_effect = lambda service_id: {
            CommonServiceID.WORK_AREAS: work_area_service,
            CommonServiceID.NAVIGATION: navigation,
        }[service_id]
        provider = PaintRobotSystemCalibrationProvider(robot_system)

        calibration_navigation = provider.build_calibration_navigation()
        calibration_navigation.move_to_calibration_position()

        work_area_service.set_active_area_id.assert_called_once_with("spray")


class TestPaintTargetFrames(unittest.TestCase):
    def test_build_frames_uses_navigation_positions_and_height_correction(self):
        navigation = MagicMock()
        navigation.get_group_position.side_effect = lambda name: {
            "SRC": [1, 2, 3, 4, 5, 6],
            "DST": [7, 8, 9, 10, 11, 12],
        }[name]
        definitions = [
            TargetFrameDefinition(
                name="frame_a",
                work_area_id="paint",
                source_navigation_group="SRC",
                target_navigation_group="DST",
                use_height_correction=True,
            )
        ]

        frames = build_paint_target_frames(
            definitions,
            navigation,
            height_correction=lambda area_id: f"hc:{area_id}",
        )

        frame = frames["frame_a"]
        self.assertEqual("paint", frame.work_area_id)
        self.assertEqual("hc:paint", frame.height_correction)
        self.assertIsNotNone(frame.mapper)
        self.assertEqual({"x": 1.0, "y": 2.0, "rz": 6.0}, vars(frame.mapper.source_pose))
        self.assertEqual({"x": 7.0, "y": 8.0, "rz": 12.0}, vars(frame.mapper.target_pose))

    def test_build_frames_returns_none_mapper_when_navigation_missing_or_invalid(self):
        definitions = [
            TargetFrameDefinition(name="frame_a", work_area_id="paint"),
            TargetFrameDefinition(
                name="frame_b",
                work_area_id="paint",
                source_navigation_group="SRC",
                target_navigation_group="DST",
            ),
        ]
        navigation = MagicMock()
        navigation.get_group_position.return_value = None

        frames = build_paint_target_frames(definitions, navigation)

        self.assertIsNone(frames["frame_a"].mapper)
        self.assertIsNone(frames["frame_b"].mapper)


class TestPaintTargetRegistry(unittest.TestCase):
    def test_build_point_registry_offsets_points_relative_to_camera(self):
        registry = build_paint_point_registry(
            [
                {"name": "camera", "x_mm": 10.0, "y_mm": 20.0},
                {"name": "tool", "x_mm": 16.0, "y_mm": 28.0},
            ]
        )

        camera = registry.by_name("camera")
        tool = registry.by_name("tool")
        self.assertEqual((0.0, 0.0), (camera.offset_x, camera.offset_y))
        self.assertEqual((6.0, 8.0), (tool.offset_x, tool.offset_y))


class TestPaintTargetingProvider(unittest.TestCase):
    def _make_robot_system(self):
        targeting = SimpleNamespace(
            frames=[
                TargetFrameDefinition(
                    name="frame_a",
                    work_area_id="paint",
                    source_navigation_group="persisted_src",
                    target_navigation_group="persisted_dst",
                    use_height_correction=True,
                    display_name="Persisted",
                ),
                TargetFrameDefinition(
                    name="frame_extra",
                    work_area_id="extra",
                    source_navigation_group="x",
                    target_navigation_group="y",
                    use_height_correction=False,
                    display_name="Extra",
                ),
            ],
            points=[
                SimpleNamespace(name="tool", display_name="Tool Persisted", x_mm=3.0, y_mm=4.0),
                SimpleNamespace(name="extra", display_name="Extra", x_mm=9.0, y_mm=10.0),
            ],
        )
        settings_service = MagicMock()
        settings_service.get.return_value = targeting
        return SimpleNamespace(
            _settings_service=settings_service,
            _height_measuring_service="height-service",
            _navigation="navigation-service",
            get_target_frame_definitions=lambda: [
                TargetFrameDefinition(
                    name="frame_a",
                    work_area_id="paint",
                    source_navigation_group="src",
                    target_navigation_group="dst",
                    use_height_correction=False,
                    display_name="Frame A",
                )
            ],
            get_target_point_definitions=lambda: [
                SimpleNamespace(name="tool", display_name="Tool"),
                SimpleNamespace(name="camera", display_name="Camera"),
            ],
        )

    def test_frame_definitions_merge_persisted_and_declared_data(self):
        provider = PaintRobotSystemTargetingProvider(self._make_robot_system())

        frames = provider._frame_definitions()

        self.assertEqual(2, len(frames))
        self.assertEqual("persisted_src", frames[0].source_navigation_group)
        self.assertEqual("persisted_dst", frames[0].target_navigation_group)
        self.assertTrue(frames[0].use_height_correction)
        self.assertEqual("frame_extra", frames[1].name)

    def test_point_definitions_merge_declared_and_persisted_data(self):
        provider = PaintRobotSystemTargetingProvider(self._make_robot_system())

        points = provider._point_definitions()

        self.assertEqual("Tool Persisted", points[0]["display_name"])
        self.assertEqual(3.0, points[0]["x_mm"])
        self.assertEqual(4.0, points[0]["y_mm"])
        self.assertEqual("camera", points[1]["name"])
        self.assertEqual("extra", points[2]["name"])

    def test_build_frames_and_lookup_helpers_delegate_to_shared_builders(self):
        robot_system = self._make_robot_system()
        provider = PaintRobotSystemTargetingProvider(robot_system)
        built_frames = {
            "frame_a": SimpleNamespace(work_area_id="paint"),
            "frame_b": SimpleNamespace(work_area_id="extra"),
        }

        captured = {}

        def _build_frames(definitions, navigation, height_correction):
            captured["navigation"] = navigation
            captured["height_correction"] = height_correction("paint")
            return built_frames

        with (
            patch("src.robot_systems.paint.targeting.provider.build_paint_target_frames", side_effect=_build_frames) as build_frames,
            patch("src.robot_systems.paint.targeting.provider.HeightCorrectionService", side_effect=lambda svc, area_id="": f"hc:{svc}:{area_id}"),
        ):
            frames = provider.build_frames()
            frame = provider.get_frame_for_work_area("paint")
            area = provider.get_work_area_for_frame("frame_b")

        self.assertIs(frames, built_frames)
        self.assertIs(frame, built_frames["frame_a"])
        self.assertEqual("extra", area)
        self.assertTrue(build_frames.called)
        self.assertEqual("navigation-service", captured["navigation"])
        self.assertEqual("hc:height-service:paint", captured["height_correction"])

    def test_target_options_and_default_name_follow_definitions(self):
        provider = PaintRobotSystemTargetingProvider(self._make_robot_system())

        self.assertEqual(
            [("Tool Persisted", "tool"), ("Camera", "camera"), ("Extra", "extra")],
            provider.get_target_options(),
        )
        self.assertEqual("tool", provider.get_default_target_name())


if __name__ == "__main__":
    unittest.main()
