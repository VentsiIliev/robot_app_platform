import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.magazine_load_service import (
    PaintMagazineLoadService,
)


class TestMagazineReleasePose(unittest.TestCase):
    def test_release_center_uses_configured_image_size_without_capture_frame(self) -> None:
        work_areas = MagicMock()
        work_areas.get_work_area.return_value = [
            (0.25, 0.25),
            (0.75, 0.25),
            (0.75, 0.75),
            (0.25, 0.75),
        ]
        service = PaintMagazineLoadService.__new__(PaintMagazineLoadService)
        service._work_area_service = work_areas
        service._release_work_area_id = "paint"
        service._release_image_size_getter = lambda: (1280, 720)

        center = service._release_work_area_center_px(frame=None)

        self.assertEqual((640.0, 360.0), center)
        work_areas.get_work_area.assert_called_once_with("paint")

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
