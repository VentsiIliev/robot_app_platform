from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

import numpy as np
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication

from src.applications.work_area_settings.view.work_area_settings_view import (
    WorkAreaSettingsView,
)
from src.applications.work_area_settings.controller.work_area_settings_controller import (
    WorkAreaSettingsController,
)
from src.shared_contracts.declarations import WorkAreaDefinition


class WorkAreaSettingsViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.view = WorkAreaSettingsView(
            [WorkAreaDefinition("paint", "Paint", "#ff8800", supports_brightness_roi=True)]
        )
        self.view.update_camera_view(np.zeros((100, 200, 3), dtype=np.uint8))
        self.view.set_area_corners(
            "paint", [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
        )

    def tearDown(self) -> None:
        self.view.close()

    def test_corner_nudge_uses_frame_pixels_and_reset_restores_saved_roi(self) -> None:
        self.view._step_group.button(5).setChecked(True)
        self.view._right_button.click()

        self.assertAlmostEqual(self.view.get_area_corners("paint")[0][0], 0.125)
        self.assertTrue(self.view._reset_btn.isEnabled())
        self.view._reset_btn.click()
        self.assertAlmostEqual(self.view.get_area_corners("paint")[0][0], 0.1)
        self.assertFalse(self.view._reset_btn.isEnabled())

    def test_roi_role_and_zoom_controls_use_shared_camera_view(self) -> None:
        self.assertTrue(self.view._preview_label._toolbar.isHidden())
        self.view._brightness_btn.click()
        self.assertEqual(self.view._active_area_key, "paint__brightness")
        self.view._zoom_in.click()
        self.assertEqual(self.view._zoom_value.text(), "130%")
        self.view._zoom_reset.click()
        self.assertEqual(self.view._zoom_value.text(), "100%")

    def test_step_buttons_do_not_overlap_the_direction_pad(self) -> None:
        self.view.resize(1280, 900)
        self.view.show()
        self.app.processEvents()

        direction_buttons = (
            self.view._up_button,
            self.view._down_button,
            self.view._left_button,
            self.view._right_button,
        )
        for direction in direction_buttons:
            direction_rect = QRect(
                direction.mapTo(self.view, QPoint(0, 0)), direction.size()
            )
            for step in self.view._step_buttons:
                step_rect = QRect(step.mapTo(self.view, QPoint(0, 0)), step.size())
                self.assertFalse(direction_rect.intersects(step_rect))



class WorkAreaSettingsControllerTests(unittest.TestCase):
    def test_vision_state_event_uses_state_value(self) -> None:
        controller = WorkAreaSettingsController.__new__(WorkAreaSettingsController)
        controller._bridge = MagicMock()

        controller._on_service_state_raw({"id": "vision_service", "state": "idle"})

        controller._bridge.vision_state.emit.assert_called_once_with("idle")

    def test_saved_roi_becomes_reset_baseline_only_after_success(self) -> None:
        controller = WorkAreaSettingsController.__new__(WorkAreaSettingsController)
        controller._active = True
        controller._view = MagicMock()
        controller._model = MagicMock()
        controller._logger = MagicMock()
        controller._view.get_area_corners.return_value = [(0.1, 0.1)] * 4
        controller._model.save_work_area.return_value = (False, "failed")

        controller._on_save_area("paint")
        controller._view.mark_area_saved.assert_not_called()

        controller._model.save_work_area.return_value = (True, "saved")
        controller._on_save_area("paint")
        controller._view.mark_area_saved.assert_called_once_with("paint")


if __name__ == "__main__":
    unittest.main()
