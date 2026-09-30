from __future__ import annotations

import logging
import os
import time
import unittest
from unittest.mock import MagicMock

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.robot_systems.paint.applications.paint_adjustment import PaintAdjustmentFactory
from src.robot_systems.paint.applications.paint_adjustment.service.stub_paint_adjustment_service import (
    StubPaintAdjustmentService,
)
from src.robot_systems.paint.applications.paint_adjustment.service.i_paint_adjustment_service import PaintHeadDialConfig
from src.robot_systems.paint.applications.paint_adjustment.dial_geometry import dial_angle_for_value
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem
from src.shared_contracts.events.vision_events import CameraTopics


class PaintAdjustmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_registered_in_production_folder(self) -> None:
        specs = [
            spec
            for spec in PaintRobotSystem.shell.applications
            if spec.name == "PaintAdjustment"
        ]
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].folder_id, 1)

    def test_dial_maps_presets_evenly_and_interpolates_register_values(self) -> None:
        self.assertEqual(
            [dial_angle_for_value(45 + 38 * (6 - setting), 45, 38, 6)
             for setting in range(1, 7)],
            [-90, -30, 30, 90, 150, 210],
        )
        self.assertEqual(dial_angle_for_value(216, 45, 38, 6), -60)
        self.assertIsNone(dial_angle_for_value(236, 45, 38, 6))

    def test_finish_enabled_after_partial_section_only_at_inspection(self) -> None:
        view = PaintAdjustmentFactory().build(StubPaintAdjustmentService(), messaging=MagicMock())
        view.set_cycle_state("running")
        view.set_adjustment_status("inspect", 0.0, 25.0)
        self.assertFalse(view._finish_button.isEnabled())
        view.set_adjustment_status("moving", 10.0, 25.0)
        self.assertFalse(view._finish_button.isEnabled())
        view.set_adjustment_status("inspect", 10.0, 25.0)
        self.assertTrue(view._finish_button.isEnabled())
        self.assertTrue(view._next_button.isEnabled())
        view.clean_up()

    def test_waiting_for_workpiece_is_visible_and_clears_when_found(self) -> None:
        view = PaintAdjustmentFactory().build(StubPaintAdjustmentService(), messaging=MagicMock())
        view.set_cycle_state("running")
        view.set_adjustment_status("waiting_for_workpiece", 0.0, 0.0)
        self.assertIn("No workpiece found", view._cycle_note.text())
        self.assertFalse(view._next_button.isEnabled())
        self.assertFalse(view._finish_button.isEnabled())
        view.set_adjustment_status("starting", 0.0, 0.0)
        self.assertNotIn("No workpiece found", view._cycle_note.text())
        view.clean_up()

    def test_auxiliary_subscription_preview_buttons_and_cleanup(self) -> None:
        broker = MagicMock()
        view = PaintAdjustmentFactory().build(
            StubPaintAdjustmentService(), messaging=broker
        )
        controller = view._controller
        self._wait_for_position_read(controller)
        self.assertEqual(view._dial.actual_value, 121)
        self.assertFalse(view._dial.grab().isNull())
        self.assertTrue(view._cycle_button.isEnabled())
        view._cycle_button.click()
        deadline = time.monotonic() + 1.0
        while controller._cycle_start_pending and time.monotonic() < deadline:
            self._app.processEvents()
            time.sleep(0.005)
        self.assertFalse(controller._cycle_start_pending)
        self.assertFalse(view._cycle_button.isEnabled())
        self.assertIn("Inspect", view._cycle_note.text())
        self.assertFalse(view._next_button.isEnabled())
        self.assertTrue(view._finish_button.isEnabled())
        view._finish_button.click()
        deadline = time.monotonic() + 1.0
        while controller._cycle_start_pending and time.monotonic() < deadline:
            self._app.processEvents()
            time.sleep(0.005)
        self.assertFalse(controller._cycle_start_pending)
        self.assertTrue(view._cycle_button.isEnabled())
        topic = CameraTopics.frame("auxiliary")
        broker.subscribe.assert_any_call(topic, controller._on_frame)
        broker.subscribe.assert_any_call(controller._process_topic, controller._on_process_state)

        frame = np.zeros((8, 12, 3), dtype=np.uint8)
        controller._on_frame({"image": frame})
        controller._display_latest_frame()
        self.assertIsNotNone(view._preview.pixmap())
        for _ in range(20):
            controller._display_latest_frame()
        self.assertTrue(view._preview.pixmap().isNull())
        controller._on_frame({"image": frame})
        controller._display_latest_frame()
        self.assertIsNotNone(view._preview.pixmap())

        with self.assertLogs(
            "src.robot_systems.paint.applications.paint_adjustment.controller.paint_adjustment_controller",
            level=logging.INFO,
        ) as logs:
            view._step_input.setValue(2)
            view._more_button.click()
            self._wait_for_action(controller)
            self.assertIn("123", view._action_note.text())
            view._step_input.setValue(1)
            view._less_button.click()
            self._wait_for_action(controller)
            self.assertIn("122", view._action_note.text())
            view._preset_buttons[1].click()
            self._wait_for_action(controller)
            self.assertIn("197", view._action_note.text())
        self.assertTrue(any("more" in line for line in logs.output))
        self.assertTrue(any("less" in line for line in logs.output))
        self.assertTrue(any("setting 2" in line for line in logs.output))

        controller._model._service.get_dial_config = MagicMock(
            return_value=PaintHeadDialConfig(45, 38, 8, True)
        )
        controller._refresh_preset_configuration()
        self.assertEqual(len(view._preset_buttons), 8)

        view.set_action_result(-1, 2, wrote=False, relative=True)
        self.assertIn("delta -1", view._action_note.text())
        view.set_action_result(235, 2, wrote=False, relative=False)
        self.assertIn("write 235", view._action_note.text())
        self.assertEqual(view._dial.preview_value, 235)
        self.assertEqual(view._dial.actual_value, 197)

        view.clean_up()
        broker.unsubscribe.assert_any_call(topic, controller._on_frame)
        broker.unsubscribe.assert_any_call(controller._process_topic, controller._on_process_state)
        self.assertFalse(controller._timer.isActive())

    def _wait_for_action(self, controller) -> None:
        deadline = time.monotonic() + 1.0
        while controller._action_pending and time.monotonic() < deadline:
            self._app.processEvents()
            time.sleep(0.005)
        self.assertFalse(controller._action_pending)

    def _wait_for_position_read(self, controller) -> None:
        deadline = time.monotonic() + 1.0
        while controller._position_read_pending and time.monotonic() < deadline:
            self._app.processEvents()
            time.sleep(0.005)
        self.assertFalse(controller._position_read_pending)


if __name__ == "__main__":
    unittest.main()
