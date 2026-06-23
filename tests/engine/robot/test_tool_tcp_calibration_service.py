import math
import unittest

import numpy as np

from src.engine.robot.calibration.tool_tcp_calibration_data import ToolTcpCalibrationResult
from src.engine.robot.calibration.tool_tcp_calibration_service import ToolTcpCalibrationService


def _rotation_matrix_xyz_degrees(rx: float, ry: float, rz: float) -> np.ndarray:
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    rx_m = np.asarray([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float64)
    ry_m = np.asarray([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float64)
    rz_m = np.asarray([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    return rz_m @ ry_m @ rx_m


def _pose_for(tool_offset_xyz: np.ndarray, pivot_point: np.ndarray, orientation: tuple[float, float, float]) -> list[float]:
    rotation = _rotation_matrix_xyz_degrees(*orientation)
    translation = pivot_point - rotation @ tool_offset_xyz
    return [*translation.tolist(), *orientation]


class _FakeRobot:
    def __init__(self, poses: list[list[float]] | None = None):
        self.poses = list(poses or [])
        self.position_calls = 0
        self.flange_calls = 0
        self.stop_calls = 0

    def get_current_position(self):
        self.position_calls += 1
        return list(self.poses.pop(0))

    def get_current_flange_position(self):
        self.flange_calls += 1
        return list(self.poses.pop(0))

    def stop_motion(self) -> bool:
        self.stop_calls += 1
        return True


class _FakeToolRegistry:
    def __init__(self, ok: bool = True, message: str = "ok"):
        self.ok = ok
        self.message = message
        self.calls = []

    def update_tool(self, tool_id, name, transform, *, persist):
        self.calls.append((tool_id, name, list(transform), persist))
        return self.ok, self.message


class TestToolTcpCalibrationService(unittest.TestCase):
    def test_captures_solves_and_saves_tool_offset(self):
        tool_offset = np.asarray([12.5, -8.0, 93.25], dtype=np.float64)
        pivot = np.asarray([300.0, -120.0, 450.0], dtype=np.float64)
        poses = [
            _pose_for(tool_offset, pivot, orientation)
            for orientation in [
                (0.0, 0.0, 0.0),
                (20.0, 0.0, 0.0),
                (-20.0, 10.0, 0.0),
                (15.0, -15.0, 30.0),
                (-10.0, 20.0, -35.0),
                (30.0, -10.0, 45.0),
            ]
        ]
        robot = _FakeRobot(poses)
        registry = _FakeToolRegistry()
        service = ToolTcpCalibrationService(robot_service=robot, tool_registry_client=registry)

        service.start(1)
        for _ in range(6):
            service.capture_sample()
        result = service.solve()
        ok, message = service.save(result)

        self.assertTrue(ok)
        self.assertIn("tool_id=1", message)
        np.testing.assert_allclose(result.tool_offset[:3], tool_offset, atol=1e-9)
        self.assertEqual(robot.flange_calls, 6)
        self.assertEqual(robot.position_calls, 0)
        self.assertEqual(
            registry.calls,
            [(1, "TOOL_1", list(result.tool_offset), True)],
        )

    def test_uses_explicit_flange_pose_provider_before_robot_service(self):
        pose = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        robot = _FakeRobot([pose])
        service = ToolTcpCalibrationService(
            robot_service=robot,
            flange_pose_provider=lambda: pose,
        )

        service.start(2)
        sample = service.capture_sample()

        self.assertEqual(sample.flange_pose, tuple(pose))
        self.assertEqual(robot.flange_calls, 0)
        self.assertEqual(robot.position_calls, 0)

    def test_capture_requires_start(self):
        service = ToolTcpCalibrationService(flange_pose_provider=lambda: [0.0] * 6)

        with self.assertRaisesRegex(RuntimeError, "not been started"):
            service.capture_sample()

    def test_save_requires_registry_client(self):
        service = ToolTcpCalibrationService(flange_pose_provider=lambda: [0.0] * 6)
        service.start(1)

        ok, message = service.save()

        self.assertFalse(ok)
        self.assertIn("not configured", message)

    def test_save_reports_registry_failure(self):
        registry = _FakeToolRegistry(ok=False, message="write failed")
        service = ToolTcpCalibrationService(
            tool_registry_client=registry,
            flange_pose_provider=lambda: [0.0] * 6,
        )
        service.start(5)
        result = ToolTcpCalibrationResult.from_values(
            tool_offset=[1.0, 2.0, 3.0, 0.0, 0.0, 0.0],
            pivot_point=[10.0, 20.0, 30.0],
            residual_rms_mm=0.1,
            residual_max_mm=0.2,
            sample_count=6,
        )

        ok, message = service.save(result)

        self.assertFalse(ok)
        self.assertIn("write failed", message)

    def test_stop_marks_session_stopped_and_stops_robot(self):
        robot = _FakeRobot()
        service = ToolTcpCalibrationService(robot_service=robot, flange_pose_provider=lambda: [0.0] * 6)
        service.start(1)

        service.stop()

        self.assertEqual(robot.stop_calls, 1)
        with self.assertRaisesRegex(RuntimeError, "stopped"):
            service.capture_sample()


if __name__ == "__main__":
    unittest.main()
