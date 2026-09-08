import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.engine.robot.plane_pose_mapper import PlanePose, PlanePoseMapper
from src.engine.robot.targeting.end_effector_point import EndEffectorPoint
from src.engine.robot.targeting.point_registry import PointRegistry
from src.engine.robot.targeting.target_frame import TargetFrame
from src.engine.robot.targeting.vision_pose_request import VisionPoseRequest
from src.engine.robot.targeting.vision_target_resolver import VisionTargetResolver
from src.engine.vision.calibration_vision_settings import CoordinateCalibrationProfile
from src.robot_systems.base_robot_system import BaseRobotSystem
from src.shared_contracts.declarations import TargetFrameDefinition, WorkAreaDefinition


class _Transformer:
    def __init__(self, x_offset=0.0):
        self.x_offset = x_offset

    def transform(self, x, y):
        return x + self.x_offset, y

    def is_available(self):
        return True

    def reload(self):
        return True

    def transform_to_tcp(self, x, y):
        return self.transform(x, y)

    def inverse_transform(self, x, y):
        return x - self.x_offset, y


def _request():
    return VisionPoseRequest(
        x_pixels=1.0,
        y_pixels=2.0,
        z_mm=0.0,
        rx_degrees=0.0,
        ry_degrees=0.0,
        rz_degrees=0.0,
    )


class _RoutingSystem(BaseRobotSystem):
    work_areas = [
        WorkAreaDefinition("paint", "Paint", "#000000"),
        WorkAreaDefinition("orphan", "Orphan", "#000000"),
    ]
    target_frames = [TargetFrameDefinition("calibration", work_area_id="paint")]

    def on_start(self):
        pass

    def on_stop(self):
        pass


class TestPerAreaCoordinateCalibration(unittest.TestCase):
    def setUp(self):
        self.registry = PointRegistry([EndEffectorPoint("camera", 0.0, 0.0)])
        mapper = PlanePoseMapper(PlanePose(0.0, 0.0, 0.0), PlanePose(100.0, 0.0, 0.0))
        self.frames = {
            "calibration": TargetFrame("calibration", work_area_id="paint"),
            "magazine": TargetFrame("magazine", work_area_id="magazine", mapper=mapper),
        }

    def test_global_mode_preserves_existing_mapper(self):
        resolver = VisionTargetResolver(_Transformer(), self.registry, frames=self.frames)
        result = resolver.resolve(_request(), self.registry.by_name("camera"), frame="magazine")
        self.assertEqual(result.plane_xy, (101.0, 2.0))

    def test_local_profile_skips_mapper_when_referenced_to_target_frame(self):
        resolver = VisionTargetResolver(
            _Transformer(),
            self.registry,
            frames=self.frames,
            calibration_mode="per_area",
            profile_transformers={"magazine_local": _Transformer(10.0)},
            work_area_profile_ids={"magazine": "magazine_local"},
            profile_reference_frames={"magazine_local": "magazine"},
        )
        result = resolver.resolve(_request(), self.registry.by_name("camera"), frame="magazine")
        self.assertEqual(result.plane_xy, (11.0, 2.0))

    def test_explicit_global_profile_can_be_shared_by_an_area(self):
        global_transformer = _Transformer()
        resolver = VisionTargetResolver(
            global_transformer,
            self.registry,
            frames=self.frames,
            calibration_mode="per_area",
            profile_transformers={"global": global_transformer},
            work_area_profile_ids={"magazine": "global"},
            profile_reference_frames={"global": "calibration"},
        )
        result = resolver.resolve(_request(), self.registry.by_name("camera"), frame="magazine")
        self.assertEqual(result.plane_xy, (101.0, 2.0))

    def test_unassigned_area_fails_in_per_area_mode(self):
        resolver = VisionTargetResolver(
            _Transformer(), self.registry, frames=self.frames, calibration_mode="per_area"
        )
        with self.assertRaisesRegex(RuntimeError, "no assigned calibration profile"):
            resolver.resolve(_request(), self.registry.by_name("camera"), frame="magazine")

    def test_frame_lookup_is_case_and_whitespace_insensitive(self):
        resolver = VisionTargetResolver(_Transformer(), self.registry, frames=self.frames)
        result = resolver.resolve(
            _request(), self.registry.by_name("camera"), frame=" Magazine "
        )
        self.assertEqual(result.plane_xy, (101.0, 2.0))

    def test_custom_global_reference_frame_can_be_reused(self):
        global_transformer = _Transformer()
        resolver = VisionTargetResolver(
            global_transformer,
            self.registry,
            frames=self.frames,
            calibration_mode="per_area",
            profile_transformers={"global": global_transformer},
            work_area_profile_ids={"magazine": "global"},
            profile_reference_frames={"global": "origin"},
            global_reference_frame="origin",
        )
        result = resolver.resolve(_request(), self.registry.by_name("camera"), frame="magazine")
        self.assertEqual(result.plane_xy, (101.0, 2.0))

    def test_unused_incomplete_profile_does_not_block_assigned_global_profile(self):
        system = _RoutingSystem()
        system._settings_service = MagicMock()
        system._settings_service.get.return_value = SimpleNamespace(
            coordinate_calibration_mode="per_area",
            coordinate_calibration_profiles={
                "future": CoordinateCalibrationProfile(matrix_path="")
            },
            work_area_calibration_profiles={"paint": "global"},
        )

        routing = system._build_coordinate_calibration_routing(_Transformer())

        self.assertEqual(routing["work_area_profile_ids"], {"paint": "global"})
        self.assertNotIn("future", routing["profile_transformers"])

    def test_assignment_requires_a_target_frame(self):
        system = _RoutingSystem()
        system._settings_service = MagicMock()
        system._settings_service.get.return_value = SimpleNamespace(
            coordinate_calibration_mode="per_area",
            coordinate_calibration_profiles={},
            work_area_calibration_profiles={"orphan": "global"},
        )

        with self.assertRaisesRegex(ValueError, "no target frame"):
            system._build_coordinate_calibration_routing(_Transformer())


if __name__ == "__main__":
    unittest.main()
