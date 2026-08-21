import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.magazine_load_service import (
    PaintMagazineLoadService,
)


class TestMagazineReleasePose(unittest.TestCase):
    def test_release_z_overrides_calibration_pose_without_changing_orientation(self) -> None:
        service = PaintMagazineLoadService.__new__(PaintMagazineLoadService)
        service._release_work_area_id = "paint"
        service._release_frame_name = "calibration"
        service._target_point_name = "tool"
        service._release_work_area_center_px = MagicMock(return_value=(100.0, 200.0))
        resolver = MagicMock()
        resolver.registry.by_name.return_value = object()
        resolver.resolve.return_value = SimpleNamespace(final_xy=(11.0, 22.0))
        service._resolver = MagicMock(return_value=resolver)

        pose = service._resolve_work_area_center_release_pose(
            base_pose=[-29.0, 217.0, 200.076, -178.0, -0.028, 0.098],
            frame=SimpleNamespace(shape=(480, 640, 3)),
            release_z_mm=50.0,
        )

        self.assertEqual(pose, [11.0, 22.0, 50.0, -178.0, -0.028, 0.098])
        request = resolver.resolve.call_args.args[0]
        self.assertEqual(request.z_mm, 50.0)


if __name__ == "__main__":
    unittest.main()
