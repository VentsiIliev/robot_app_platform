from __future__ import annotations

import logging
import os
import time
import unittest
from threading import Event
from unittest.mock import MagicMock

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.robot_systems.paint.applications.paint_adjustment import PaintAdjustmentFactory
from src.robot_systems.paint.applications.paint_adjustment.service.stub_paint_adjustment_service import (
    StubPaintAdjustmentService,
)
from src.robot_systems.paint.applications.paint_adjustment.service.i_paint_adjustment_service import PaintHeadDialConfig
from src.robot_systems.paint.applications.paint_adjustment.dial_geometry import (
    dial_angle_for_value, dial_setting_for_value, dial_value_for_angle,
)
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
        self.assertEqual(dial_value_for_angle(-60, 45, 38, 6), 216)
        self.assertEqual(dial_value_for_angle(-30, 45, 38, 6), 197)
        self.assertAlmostEqual(dial_setting_for_value(212, 45, 38, 6), 1 + 23 / 38)
        self.assertEqual(dial_setting_for_value(235, 45, 38, 6), 1.0)
        self.assertEqual(dial_setting_for_value(197, 45, 38, 6), 2.0)
        self.assertIsNone(dial_setting_for_value(236, 45, 38, 6))

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

    def test_quick_step_buttons_follow_paint_head_availability(self) -> None:
        view = PaintAdjustmentFactory().build(StubPaintAdjustmentService(), messaging=MagicMock())
        view.set_paint_head_available(True)
        view._step_buttons[2].click()
        self.assertEqual(view._step_input.value(), 3)
        self.assertTrue(view._step_buttons[2].isChecked())
        view.set_action_pending()
        self.assertTrue(all(not button.isEnabled() for button in view._step_buttons))
        view.clean_up()

    def test_more_paint_repeats_while_held_and_stops_on_release(self) -> None:
        service = StubPaintAdjustmentService()
        original_adjust = service.adjust_paint_by_register_units
        service.adjust_paint_by_register_units = MagicMock(wraps=original_adjust)
        view = PaintAdjustmentFactory().build(service, messaging=MagicMock())
        self._wait_for_position_read(view._controller)
        view.show()
        self._app.processEvents()
        view._step_input.setValue(2)

        QTest.mousePress(view._more_button, Qt.MouseButton.LeftButton)
        QTest.qWait(850)
        QTest.mouseRelease(view._more_button, Qt.MouseButton.LeftButton)
        self._wait_for_action(view._controller)
        call_count = service.adjust_paint_by_register_units.call_count
        self.assertGreaterEqual(call_count, 2)
        self.assertTrue(all(call.args == ("more", 2) for call in service.adjust_paint_by_register_units.call_args_list))
        self.assertEqual(view._dial.actual_value, 121 + 2 * call_count)
        QTest.qWait(350)
        self.assertEqual(service.adjust_paint_by_register_units.call_count, call_count)
        view.clean_up()

    def test_invalid_position_read_shows_connection_guidance(self) -> None:
        service = StubPaintAdjustmentService()
        service.read_current_position = MagicMock(
            side_effect=ValueError("Paint-head position 0 is outside the configured range")
        )
        with self.assertLogs(
            "src.robot_systems.paint.applications.paint_adjustment.controller.paint_adjustment_controller",
            level=logging.ERROR,
        ):
            view = PaintAdjustmentFactory().build(service, messaging=MagicMock())
            self._wait_for_position_read(view._controller)
        self.assertIn("communication issue", view._position_note.text())
        self.assertIn("unplugged or missing", view._position_note.text())
        self.assertIn("position 0", view._position_note.toolTip())
        self.assertTrue(view._read_position_button.isEnabled())
        view.clean_up()

    def test_dragging_dial_sends_positions_before_release(self) -> None:
        service = StubPaintAdjustmentService()
        original_go_to_position = service.go_to_position
        service.go_to_position = MagicMock(wraps=original_go_to_position)
        view = PaintAdjustmentFactory().build(service, messaging=MagicMock())
        self._wait_for_position_read(view._controller)
        view.resize(1400, 900)
        view.show()
        self._app.processEvents()
        dial = view._dial
        radius = min(dial.width(), dial.height()) // 2 - 42
        center = QPoint(dial.width() // 2, dial.height() // 2)
        top = QPoint(center.x(), center.y() - radius)
        between = QPoint(center.x() + radius // 2, center.y() - round(radius * 0.866))
        QTest.mousePress(dial, Qt.MouseButton.LeftButton, pos=top)
        self._wait_for_action(view._controller)
        service.go_to_position.assert_called_once_with(235)
        QTest.mouseMove(dial, between)
        self._wait_for_action(view._controller)
        self.assertEqual(dial.preview_value, 216)
        self.assertEqual(dial.format_position(dial.preview_value), "1.5")
        self.assertEqual(service.go_to_position.call_args_list[-1].args, (216,))
        QTest.mouseRelease(dial, Qt.MouseButton.LeftButton, pos=between)
        self._wait_for_action(view._controller)
        self.assertEqual(service.go_to_position.call_count, 2)
        self.assertEqual(dial.actual_value, 216)
        self.assertIn("1.5", view._position_note.text())
        view.clean_up()

    def test_dial_sends_latest_release_target_after_slow_write(self) -> None:
        service = StubPaintAdjustmentService()
        original_go_to_position = service.go_to_position
        first_started = Event()
        finish_first = Event()

        def slow_first_position(position: int):
            if position == 235:
                first_started.set()
                finish_first.wait(2.0)
            return original_go_to_position(position)

        service.go_to_position = MagicMock(side_effect=slow_first_position)
        view = PaintAdjustmentFactory().build(service, messaging=MagicMock())
        try:
            self._wait_for_position_read(view._controller)
            view.resize(1400, 900)
            view.show()
            self._app.processEvents()
            dial = view._dial
            radius = min(dial.width(), dial.height()) // 2 - 42
            center = QPoint(dial.width() // 2, dial.height() // 2)
            top = QPoint(center.x(), center.y() - radius)
            between = QPoint(center.x() + radius // 2, center.y() - round(radius * 0.866))
            second = QPoint(center.x() + round(radius * 0.866), center.y() - radius // 2)

            QTest.mousePress(dial, Qt.MouseButton.LeftButton, pos=top)
            self.assertTrue(first_started.wait(1.0))
            QTest.mouseMove(dial, between)
            QTest.mouseMove(dial, second)
            QTest.mouseRelease(dial, Qt.MouseButton.LeftButton, pos=second)
            finish_first.set()
            deadline = time.monotonic() + 2.0
            while (view._controller._action_pending or
                   service.go_to_position.call_count < 2) and time.monotonic() < deadline:
                self._app.processEvents()
                time.sleep(0.005)

            self.assertEqual(
                [call.args for call in service.go_to_position.call_args_list],
                [(235,), (197,)],
            )
            self.assertEqual(dial.actual_value, 197)
        finally:
            finish_first.set()
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
            view._step_input.setValue(1)
            view._more_button.click()
            self._wait_for_action(controller)
            self.assertEqual(view._dial.actual_value, 122)
            view._step_input.setValue(2)
            view._less_button.click()
            self._wait_for_action(controller)
            self.assertEqual(view._dial.actual_value, 120)
        self.assertTrue(any("more" in line for line in logs.output))
        self.assertTrue(any("less" in line for line in logs.output))

        controller._model._service.get_dial_config = MagicMock(
            return_value=PaintHeadDialConfig(45, 38, 8, True)
        )
        controller._refresh_preset_configuration()
        self.assertEqual(view._dial._count, 8)

        view.set_action_result(-1, 2, wrote=False, relative=True)
        self.assertIn("command simulated", view._action_note.text())
        view.set_action_result(235, 2, wrote=False, relative=False)
        self.assertIn("command simulated", view._action_note.text())
        self.assertIn("3.0", view._position_note.text())
        self.assertEqual(view._dial.preview_value, 235)
        self.assertEqual(view._dial.actual_value, 120)

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
