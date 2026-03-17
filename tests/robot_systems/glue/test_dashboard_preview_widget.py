import unittest

import numpy as np
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication

from src.engine.localization.localization_service import LocalizationService
from src.robot_systems.glue.applications.dashboard.ui.dashboard_preview_widget import (
    DashboardPreviewWidget,
    PreviewDisplayMode,
)
from pathlib import Path


_TRANSLATIONS_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "robot_systems"
    / "glue"
    / "storage"
    / "translations"
)


class TestDashboardPreviewWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_live_primary_with_inset_renders_progress_thumbnail(self):
        widget = DashboardPreviewWidget(image_width=200, image_height=100, fps_ms=1000)
        widget.set_live_frame({"image": np.full((100, 200, 3), (10, 20, 30), dtype=np.uint8)})
        widget.set_progress_snapshot(
            np.full((100, 200, 3), (50, 150, 50), dtype=np.uint8),
            [],
        )
        widget.set_primary_mode(PreviewDisplayMode.LIVE)
        widget.set_inset_enabled(True)

        canvas = widget._compose_canvas()

        self.assertEqual(tuple(canvas[50, 50]), (10, 20, 30))
        self.assertEqual(tuple(canvas[20, 170]), (47, 137, 47))

    def test_progress_primary_with_inset_disabled_renders_only_progress(self):
        widget = DashboardPreviewWidget(image_width=200, image_height=100, fps_ms=1000)
        widget.set_live_frame({"image": np.full((100, 200, 3), (10, 20, 30), dtype=np.uint8)})
        widget.set_progress_snapshot(
            np.full((100, 200, 3), (50, 150, 50), dtype=np.uint8),
            [],
        )
        widget.set_primary_mode(PreviewDisplayMode.JOB_PROGRESS)
        widget.set_inset_enabled(False)

        canvas = widget._compose_canvas()

        self.assertEqual(tuple(canvas[50, 50]), (47, 137, 47))
        self.assertEqual(tuple(canvas[20, 170]), (47, 137, 47))

    def test_progress_overlay_draws_completed_and_pending_segments_with_different_colors(self):
        widget = DashboardPreviewWidget(image_width=100, image_height=100, fps_ms=1000)
        widget.set_progress_snapshot(
            np.zeros((100, 100, 3), dtype=np.uint8),
            [
                {
                    "path_index": 0,
                    "points": [(10.0, 50.0), (50.0, 50.0), (90.0, 50.0)],
                }
            ],
        )
        widget.set_progress_state(
            {
                "dispensing": {
                    "current_path_index": 0,
                    "current_point_index": 2,
                }
            }
        )

        frame = widget._build_progress_frame()

        self.assertEqual(tuple(frame[50, 20]), (88, 194, 122))
        self.assertEqual(tuple(frame[50, 70]), (67, 179, 211))

    def test_progress_overlay_uses_robot_point_for_continuous_progress(self):
        widget = DashboardPreviewWidget(image_width=100, image_height=100, fps_ms=1000)
        widget.set_progress_snapshot(
            np.zeros((100, 100, 3), dtype=np.uint8),
            [
                {
                    "path_index": 0,
                    "points": [(10.0, 50.0), (50.0, 50.0), (90.0, 50.0)],
                }
            ],
        )
        widget.set_progress_state(
            {
                "dispensing": {
                    "current_path_index": 0,
                    "current_point_index": 1,
                }
            }
        )
        widget.set_progress_robot_point((88.0, 50.0))

        frame = widget._build_progress_frame()

        self.assertEqual(tuple(frame[50, 70]), (88, 194, 122))

    def test_preview_controls_retranslate(self):
        service = LocalizationService(str(_TRANSLATIONS_DIR))
        widget = DashboardPreviewWidget(image_width=100, image_height=100, fps_ms=1000)

        service.set_language("bg")
        QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

        self.assertEqual(widget._live_btn.text(), "На живо")
        self.assertEqual(widget._progress_btn.text(), "Прогрес")
        self.assertEqual(widget._inset_btn.text(), "Мини изглед")


if __name__ == "__main__":
    unittest.main()
