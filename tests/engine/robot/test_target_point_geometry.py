import unittest

from src.engine.robot.targeting.end_effector_point import EndEffectorPoint
from src.engine.robot.targeting.jog_frame_pose_resolver import JogFramePoseResolver
from src.engine.robot.targeting.target_point_geometry import (
    command_xy_from_selected_xy,
    command_xyz_from_selected_xyz,
)
from src.engine.robot.targeting.vision_pose_request import VisionPoseRequest
from src.engine.robot.targeting.vision_target_resolver import VisionTargetResolver


class _Registry:
    def by_name(self, name):
        return EndEffectorPoint(name=name, offset_x=0.0, offset_y=100.0)

    def names(self):
        return ["tool"]


class _Transformer:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def transform(_x, _y):
        return 0.0, 0.0


class TestTargetPointGeometry(unittest.TestCase):
    def test_command_xyz_keeps_legacy_flat_rz_result(self):
        expected_x, expected_y = command_xy_from_selected_xy(
            0.0,
            0.0,
            90.0,
            point_offset_x=10.0,
            point_offset_y=20.0,
            reference_rz=0.0,
        )

        x, y, z = command_xyz_from_selected_xyz(
            0.0,
            0.0,
            0.0,
            orientation=(180.0, 0.0, 90.0),
            point_offset_x=10.0,
            point_offset_y=20.0,
            reference_orientation=(180.0, 0.0, 0.0),
        )

        self.assertAlmostEqual(expected_x, x, places=6)
        self.assertAlmostEqual(expected_y, y, places=6)
        self.assertAlmostEqual(0.0, z, places=6)

    def test_jog_ry_in_tilted_pose_keeps_selected_tool_point_fixed(self):
        resolver = JogFramePoseResolver(_Registry())
        point = EndEffectorPoint(name="tool", offset_x=0.0, offset_y=100.0)

        pose = resolver.resolve(
            [0.0, 0.0, -100.0, -90.0, 0.0, 0.0],
            "RY",
            "plus",
            10.0,
            point,
        )

        self.assertIsNotNone(pose)
        self.assertAlmostEqual(17.364818, pose[0], places=6)
        self.assertAlmostEqual(0.0, pose[1], places=6)
        self.assertAlmostEqual(-101.519225, pose[2], places=6)
        self.assertAlmostEqual(-90.0, pose[3], places=6)
        self.assertAlmostEqual(10.0, pose[4], places=6)
        self.assertAlmostEqual(0.0, pose[5], places=6)

    def test_vision_resolver_uses_ry_for_tilted_target_offsets(self):
        resolver = VisionTargetResolver(_Transformer(), _Registry())

        result = resolver.resolve(
            VisionPoseRequest(
                x_pixels=12.0,
                y_pixels=34.0,
                z_mm=0.0,
                rx_degrees=-90.0,
                ry_degrees=10.0,
                rz_degrees=0.0,
            ),
            EndEffectorPoint(name="tool", offset_x=0.0, offset_y=100.0),
        )

        pose = result.robot_pose()
        self.assertAlmostEqual(-17.364818, pose[0], places=6)
        self.assertAlmostEqual(0.0, pose[1], places=6)
        self.assertAlmostEqual(-98.480775, pose[2], places=6)
        self.assertAlmostEqual(-90.0, pose[3], places=6)
        self.assertAlmostEqual(10.0, pose[4], places=6)
        self.assertAlmostEqual(0.0, pose[5], places=6)


if __name__ == "__main__":
    unittest.main()
