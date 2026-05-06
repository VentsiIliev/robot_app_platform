from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QWidget

from pl_gui.dashboard.config import CardConfig
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.ui.paint_card_factory import (
    PaintCardFactory,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_status_card import (
    PaintStatusCard,
)
from src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view import (
    PaintDashboardView,
)


class _Signal:
    def __init__(self) -> None:
        self.connected = []
        self.emitted = []

    def connect(self, callback) -> None:
        self.connected.append(callback)

    def emit(self, *args) -> None:
        self.emitted.append(args)
        for callback in list(self.connected):
            if hasattr(callback, "emit"):
                callback.emit(*args)
            else:
                callback(*args)


class _FakeDashboardWidget(QWidget):
    def __init__(self, config=None, action_buttons=None, cards=None):
        super().__init__()
        self.config = config
        self.action_buttons = action_buttons
        self.cards = cards
        self.start_requested = _Signal()
        self.stop_requested = _Signal()
        self.pause_requested = _Signal()
        self.action_requested = _Signal()
        self.calls = []
        self.layout_manager = SimpleNamespace(main_layout=None)

    def set_trajectory_image(self, image) -> None:
        self.calls.append(("trajectory", image))

    def set_start_enabled(self, enabled: bool) -> None:
        self.calls.append(("start", enabled))

    def set_stop_enabled(self, enabled: bool) -> None:
        self.calls.append(("stop", enabled))

    def set_pause_enabled(self, enabled: bool) -> None:
        self.calls.append(("pause", enabled))

    def set_pause_text(self, text: str) -> None:
        self.calls.append(("pause_text", text))


class TestPaintDashboardUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_card_factory_builds_status_cards_with_layout_coordinates(self) -> None:
        cards = PaintCardFactory().build_cards(
            [
                CardConfig(card_id=3, label="Paint", row=1, col=2),
                CardConfig(card_id=4, label="Dry"),
            ]
        )

        self.assertEqual(len(cards), 2)
        self.assertIsInstance(cards[0][0], PaintStatusCard)
        self.assertEqual(cards[0][1:], (3, 1, 2))
        self.assertEqual(cards[1][1:], (4, None, None))

    def test_status_card_updates_state_label(self) -> None:
        card = PaintStatusCard("Paint")

        card.set_state("running")

        self.assertEqual(card._title.text(), "Paint")
        self.assertEqual(card._state.text(), "State: running")

    def test_dashboard_view_wires_inner_dashboard_and_applies_state(self) -> None:
        state = DashboardState(
            process_state="running",
            mode_label="Paint Mode",
            active_job_label="Job 12",
            status_lines=["one", "two"],
            can_start=False,
            can_stop=True,
            can_pause=True,
            pause_label="Resume",
        )

        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=["a"],
                cards=["c"],
            )

        start_cb = MagicMock()
        stop_cb = MagicMock()
        pause_cb = MagicMock()
        action_cb = MagicMock()
        reset_cb = MagicMock()
        view.start_requested.connect(start_cb)
        view.stop_requested.connect(stop_cb)
        view.pause_requested.connect(pause_cb)
        view.action_requested.connect(action_cb)
        view.reset_requested.connect(reset_cb)

        self.assertIsInstance(view._dashboard, _FakeDashboardWidget)
        self.assertEqual(view._dashboard.config.preview_aux_rows, 1)
        self.assertEqual(view._dashboard.action_buttons, ["a"])
        self.assertEqual(view._dashboard.cards, ["c"])

        view._dashboard.start_requested.emit()
        view._dashboard.stop_requested.emit()
        view._dashboard.pause_requested.emit()
        view._dashboard.action_requested.emit("custom")
        view._dashboard.action_requested.emit("reset_errors")

        self.assertEqual(view._state_label.text(), "State: idle")
        start_cb.assert_called_once_with()
        stop_cb.assert_called_once_with()
        pause_cb.assert_called_once_with()
        action_cb.assert_called_once_with("custom")
        reset_cb.assert_called_once_with()

        view.set_trajectory_image("img")
        view.apply_dashboard_state(state)

        self.assertIn(("trajectory", "img"), view._dashboard.calls)
        self.assertIn(("start", False), view._dashboard.calls)
        self.assertIn(("stop", True), view._dashboard.calls)
        self.assertIn(("pause", True), view._dashboard.calls)
        self.assertIn(("pause_text", "Resume"), view._dashboard.calls)
        self.assertEqual(view._state_label.text(), "State: running")
        self.assertEqual(view._mode_label.text(), "Mode: Paint Mode")
        self.assertEqual(view._job_label.text(), "Job: Job 12")
        self.assertEqual(view._notes.toPlainText(), "one\ntwo")

    def test_inject_aux_widget_falls_back_to_dashboard_parent_on_layout_failure(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=[],
                cards=[],
            )

        widget = QWidget()
        view._inject_aux_widget(widget)
        self.assertIs(widget.parent(), view._dashboard)
        self.assertIsNone(view.clean_up())

    def test_inject_aux_widget_uses_preview_aux_grid_when_layout_available(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=2, preview_aux_cols=3),
                action_buttons=[],
                cards=[],
            )

        aux_layout = MagicMock()
        aux_grid = SimpleNamespace(layout=MagicMock(return_value=aux_layout))
        preview_container = SimpleNamespace(
            layout=MagicMock(
                return_value=SimpleNamespace(
                    itemAt=MagicMock(return_value=SimpleNamespace(widget=MagicMock(return_value=aux_grid)))
                )
            )
        )
        top_section = SimpleNamespace(
            itemAt=MagicMock(return_value=SimpleNamespace(widget=MagicMock(return_value=preview_container)))
        )
        main_layout = SimpleNamespace(
            itemAt=MagicMock(return_value=SimpleNamespace(layout=MagicMock(return_value=top_section)))
        )
        view._dashboard.layout_manager = SimpleNamespace(main_layout=main_layout)

        widget = QWidget()
        view._inject_aux_widget(widget)

        aux_layout.addWidget.assert_called_once_with(widget, 0, 0, 2, 3)


if __name__ == "__main__":
    unittest.main()
