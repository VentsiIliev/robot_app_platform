import unittest

from src.engine.robot.targeting.end_effector_point import EndEffectorPoint
from src.engine.robot.targeting.jog_frame_pose_resolver import JogFramePoseResolver
from src.engine.robot.targeting.target_point_geometry import (
    camera_to_tcp_rotation_residual_xy,
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


class _NamedRegistry:
    def by_name(self, name):
        if name == "camera":
            return EndEffectorPoint(name="camera", offset_x=0.0, offset_y=0.0)
        return EndEffectorPoint(name="tool", offset_x=12.0, offset_y=2.0)

    def names(self):
        return ["camera", "tool"]


class _Transformer:
    @staticmethod
    def is_available():
        return True

    @staticmethod
    def transform(_x, _y):
        return 0.0, 0.0


class TestTargetPointGeometry(unittest.TestCase):
    def test_rotation_residual_interpolates_only_inside_verified_range(self):
        residuals = [
            {"angle_deg": 0.0, "x_mm": 0.0, "y_mm": 0.0},
            {"angle_deg": 90.0, "x_mm": 3.0, "y_mm": 1.0},
        ]

        self.assertEqual((1.5, 0.5), camera_to_tcp_rotation_residual_xy(residuals, 45.0))
        self.assertEqual((0.0, 0.0), camera_to_tcp_rotation_residual_xy(residuals, -5.0))
        self.assertEqual((0.0, 0.0), camera_to_tcp_rotation_residual_xy(residuals, 95.0))

    def test_command_pose_adds_verified_rotation_residual(self):
        pose = command_xyz_from_selected_xyz(
            100.0,
            200.0,
            150.0,
            orientation=(-180.0, 0.0, 90.0),
            camera_to_tcp_x_offset=10.0,
            camera_to_tcp_y_offset=0.0,
            reference_orientation=(-180.0, 0.0, 0.0),
            camera_to_tcp_rotation_residuals=[
                {"angle_deg": 0.0, "x_mm": 0.0, "y_mm": 0.0},
                {"angle_deg": 90.0, "x_mm": 3.0, "y_mm": 1.0},
            ],
        )

        self.assertEqual((113.0, 191.0, 150.0), pose)

    def test_resolver_applies_camera_base_residual_before_tool_offset(self):
        resolver = VisionTargetResolver(
            _Transformer(),
            _NamedRegistry(),
            camera_to_tcp_x_offset=10.0,
            camera_to_tcp_y_offset=0.0,
            camera_to_tcp_rotation_residuals=[
                {"angle_deg": 0.0, "x_mm": 0.0, "y_mm": 0.0},
                {"angle_deg": 90.0, "x_mm": 3.0, "y_mm": 1.0},
            ],
        )
        request = VisionPoseRequest(
            x_pixels=12.0,
            y_pixels=34.0,
            z_mm=150.0,
            rx_degrees=-180.0,
            ry_degrees=0.0,
            rz_degrees=90.0,
        )

        camera = resolver.resolve(request, resolver.registry.by_name("camera"))
        tool = resolver.resolve(request, resolver.registry.by_name("tool"))

        self.assertEqual((13.0, -9.0), camera.final_xy)
        # The taught tool vector is also its sweep pivot, so its rigid rotation
        # cancels. Camera-only verification residuals must not move the tool.
        self.assertEqual((12.0, 2.0), tool.final_xy)

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
