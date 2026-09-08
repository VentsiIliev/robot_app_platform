from __future__ import annotations

import os
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTabBar
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pl_gui.dashboard.config import CardConfig
from pl_gui.utils.utils_widgets.SwitchButton import QToggle
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardCardState, DashboardState
from src.robot_systems.paint.applications.dashboard.ui.paint_card_factory import (
    PaintCardFactory,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_info_card import (
    PaintInfoCard,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_quick_controls_panel import (
    PaintQuickControlsPanel,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_quick_access_panel import (
    PaintQuickAccessPanel,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_plate_layout import (
    PaintPlateLayout,
    _PlateCanvas,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_controls_drawer import (
    PaintControlsDrawer,
)
from src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view import (
    PaintDashboardView,
    _MAX_MESSAGE_ROWS,
)
from src.robot_systems.paint.applications.dashboard.config import (
    AuxiliaryToggleConfig,
    PAINT_DASHBOARD_ACTIONS,
    PAINT_DASHBOARD_CARDS,
    PaintDashboardConfig,
    PaintDashboardUiConfig,
)
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_view import (
    _MagazineOrderTable,
)
from src.shared_contracts.events.shell_events import ApplicationShortcut


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

    def set_action_button_enabled(self, action_id: str, enabled: bool) -> None:
        self.calls.append(("action_enabled", action_id, enabled))


class TestPaintDashboardUi(unittest.TestCase):
    def test_magazine_order_table_reorders_and_disables_available_groups(self) -> None:
        emitted = []
        table = _MagazineOrderTable(emitted.append)
        table.set_sources([
            {"movement_group_id": "Magazine Fixed Pickup", "enabled": True},
            {"position": [1, 2, 3, 4, 5, 6], "enabled": False},
            {"position": [11, 12, 13, 14, 15, 16], "enabled": False},
        ])

        self.assertTrue(table._table.alternatingRowColors())
        self.assertGreaterEqual(table._table.minimumHeight(), 180)
        self.assertIn("QTableWidget::item", table._table.styleSheet())
        self.assertFalse(table._up.isEnabled())
        self.assertFalse(table._down.isEnabled())

        table._table.selectRow(2)
        table._move_up()
        checkbox = table._table.cellWidget(1, 0).findChild(QCheckBox)
        checkbox.setChecked(True)

        self.assertEqual(
            [
                "Magazine Fixed Pickup",
                "",
                "",
            ],
            [source.get("movement_group_id", "") for source in table.get_sources()],
        )
        self.assertTrue(table.get_sources()[1]["enabled"])
        self.assertFalse(table.get_sources()[2]["enabled"])
        self.assertEqual([11.0, 12.0, 13.0, 14.0, 15.0, 16.0], table.get_sources()[1]["position"])

    def test_combined_speed_control_maps_speed_to_velocity_and_acceleration(self) -> None:
        drawer = PaintControlsDrawer([], use_combined_speed_control=True)
        drawer._unmatched_velocity.setValue(80.0)
        drawer._pass_2_use_first.setChecked(False)
        drawer._pass_2_velocity.setValue(50.0)

        payload = drawer._settings_payload()

        self.assertEqual(drawer._unmatched_velocity.minimum(), 1.0)
        self.assertEqual(drawer._unmatched_velocity_label.text(), "Speed")
        self.assertTrue(drawer._unmatched_acceleration_label.isHidden())
        self.assertEqual(payload["pass_1"]["velocity_percent"], 80.0)
        self.assertEqual(payload["pass_1"]["acceleration_percent"], 64.0)
        self.assertEqual(payload["pass_2"]["velocity_percent"], 50.0)
        self.assertEqual(payload["pass_2"]["acceleration_percent"], 25.0)

    def test_combined_speed_control_optionally_shows_live_resolved_values(self) -> None:
        drawer = PaintControlsDrawer(
            [],
            use_combined_speed_control=True,
            show_resolved_speed_values=True,
        )

        drawer._unmatched_velocity.setValue(80.0)
        drawer._pass_2_velocity.setValue(50.0)

        self.assertFalse(drawer._pass_1_resolved_speed.isHidden())
        self.assertEqual(
            drawer._pass_1_resolved_speed.text(),
            "Velocity: 80.0%  ·  Acceleration: 64.00%",
        )
        self.assertEqual(
            drawer._pass_2_resolved_speed.text(),
            "Velocity: 50.0%  ·  Acceleration: 25.00%",
        )

        drawer._unmatched_velocity.setValue(1.0)
        payload = drawer._settings_payload()
        self.assertAlmostEqual(payload["pass_1"]["acceleration_percent"], 0.01)
        self.assertEqual(
            drawer._pass_1_resolved_speed.text(),
            "Velocity: 1.0%  ·  Acceleration: 0.01%",
        )

    def test_resolved_speed_values_stay_hidden_without_combined_control(self) -> None:
        drawer = PaintControlsDrawer(
            [],
            use_combined_speed_control=False,
            show_resolved_speed_values=True,
        )

        self.assertTrue(drawer._pass_1_resolved_speed.isHidden())

    def test_combined_speed_can_map_ui_one_to_internal_ten(self) -> None:
        drawer = PaintControlsDrawer(
            [],
            use_combined_speed_control=True,
            combined_speed_minimum_percent=10.0,
            combined_acceleration_minimum_percent=1.0,
            show_resolved_speed_values=True,
        )
        drawer._unmatched_velocity.setValue(1.0)

        payload = drawer._settings_payload()

        self.assertEqual(payload["pass_1"]["velocity_percent"], 10.0)
        self.assertEqual(payload["pass_1"]["acceleration_percent"], 1.0)
        self.assertEqual(
            drawer._pass_1_resolved_speed.text(),
            "Velocity: 10.0%  ·  Acceleration: 1.00%",
        )
        drawer.set_unmatched_paint_settings(payload["pass_1"])
        self.assertEqual(drawer._unmatched_velocity.value(), 1.0)

    def test_separate_velocity_and_acceleration_controls_remain_configurable(self) -> None:
        drawer = PaintControlsDrawer([], use_combined_speed_control=False)
        drawer._unmatched_velocity.setValue(80.0)
        drawer._unmatched_acceleration.setValue(37.0)

        payload = drawer._settings_payload()

        self.assertFalse(drawer._unmatched_acceleration_label.isHidden())
        self.assertEqual(payload["pass_1"]["velocity_percent"], 80.0)
        self.assertEqual(payload["pass_1"]["acceleration_percent"], 37.0)

    def test_camera_quick_controls_use_the_same_combined_speed_mapping(self) -> None:
        panel = PaintQuickControlsPanel([], use_combined_speed_control=True)
        callback = MagicMock()
        panel.unmatched_paint_settings_requested.connect(callback)
        panel._velocity.setValue(80.0)

        panel._apply.click()

        payload = callback.call_args.args[0]
        self.assertEqual(panel._velocity.minimum(), 1.0)
        self.assertEqual(panel._velocity_label.text(), "Speed")
        self.assertEqual(payload["pass_1"]["velocity_percent"], 80.0)
        self.assertEqual(payload["pass_1"]["acceleration_percent"], 64.0)

    def test_camera_quick_controls_show_live_resolved_speed_values(self) -> None:
        panel = PaintQuickControlsPanel(
            [],
            use_combined_speed_control=True,
            show_resolved_speed_values=True,
        )

        panel._velocity.setValue(80.0)

        self.assertEqual(
            panel._resolved_speed.text(),
            "Velocity: 80.0%  ·  Acceleration: 64.00%",
        )

    def test_quick_access_pump_is_off_only_while_fan_remains_toggleable(self) -> None:
        panel = PaintQuickAccessPanel([
            AuxiliaryToggleConfig("pump", "Vacuum Pump"),
            AuxiliaryToggleConfig("fan", "Fan"),
        ])
        callback = MagicMock()
        panel.device_toggle_requested.connect(callback)

        panel.set_device_state("pump", True)
        self.assertFalse(panel._buttons["pump"].isCheckable())
        self.assertEqual(panel._buttons["pump"].text(), "Vacuum Pump: OFF")
        panel._buttons["pump"].click()
        callback.assert_called_once_with("pump", False)

        callback.reset_mock()
        self.assertTrue(panel._buttons["fan"].isCheckable())
        panel._buttons["fan"].click()
        callback.assert_called_once_with("fan", True)

    def test_quick_access_new_tray_is_visible_only_in_tray_dry_mode(self) -> None:
        panel = PaintQuickAccessPanel([])
        callback = MagicMock()
        panel.new_tray_requested.connect(callback)

        panel.set_drying_mode("auto")
        self.assertFalse(panel._new_tray.isVisible())

        panel.set_drying_mode("manual")
        self.assertFalse(panel._new_tray.isHidden())
        self.assertEqual(panel._drying_mode_button.text(), "Tray Dry")
        panel._new_tray.click()
        callback.assert_called_once_with()

        panel.set_drying_mode("demo")
        self.assertTrue(panel._new_tray.isHidden())

    def test_tray_selection_shows_painted_time_and_live_drying_duration(self) -> None:
        tray = PaintPlateLayout()
        tray.set_state({
            "width_mm": 200.0,
            "height_mm": 100.0,
            "placements": [{
                "placement_id": 1,
                "left_mm": 0.0,
                "bottom_mm": 0.0,
                "width_mm": 20.0,
                "height_mm": 30.0,
                "painted_at": "2026-09-04T11:30:15+03:00",
                "paint_pass_count": 2,
            }],
            "pending": None,
        })

        with patch(
            "src.robot_systems.paint.applications.dashboard.ui.paint_plate_layout.datetime"
        ) as clock:
            clock.fromisoformat.side_effect = datetime.fromisoformat
            clock.now.return_value = datetime.fromisoformat("2026-09-04T11:31:20+03:00")
            tray._on_placement_held(1)

        self.assertIn("Painted at: 11:30:15", tray._hint.text())
        self.assertIn("Drying for: 1m 5s", tray._hint.text())
        self.assertEqual(tray._selected_drying_value.text(), "1m 5s")
        self.assertIn("Passes: 2", tray._hint.text())
        self.assertTrue(tray._drying_timer.isActive())

    def test_tray_dry_duration_control_is_feature_gated(self) -> None:
        disabled = PaintPlateLayout(use_dry_duration=False)
        enabled = PaintPlateLayout(
            use_dry_duration=True,
            drying_duration_minutes=15,
        )

        self.assertTrue(disabled._drying_duration_box.isHidden())
        self.assertTrue(disabled._selected_drying_box.isHidden())
        self.assertIsNone(disabled._canvas._drying_duration_seconds)
        self.assertFalse(enabled._drying_duration_box.isHidden())
        self.assertFalse(enabled._selected_drying_box.isHidden())
        self.assertEqual(enabled._selected_drying_value.text(), "—")
        self.assertEqual(enabled._canvas._drying_duration_seconds, 15 * 60)
        enabled.set_editable(False, removal_editable=True)
        self.assertFalse(enabled._new_tray.isEnabled())
        self.assertTrue(enabled._remove.isEnabled())

    def test_tray_marks_workpiece_dried_after_configured_duration(self) -> None:
        from datetime import timedelta

        tray = PaintPlateLayout(use_dry_duration=True, drying_duration_minutes=10)
        now = datetime.now().astimezone()
        old = {"painted_at": (now - timedelta(minutes=11)).isoformat()}
        recent = {"painted_at": (now - timedelta(minutes=9)).isoformat()}

        self.assertTrue(tray._canvas._is_dried(old))
        self.assertFalse(tray._canvas._is_dried(recent))

    def test_tray_canvas_preserves_physical_aspect_ratio(self) -> None:
        canvas = _PlateCanvas()
        canvas.resize(600, 300)

        plate = canvas._scaled_plate_rect(200.0, 50.0)

        self.assertAlmostEqual(4.0, plate.width() / plate.height())
        self.assertAlmostEqual((canvas.width() - plate.width()) / 2.0, plate.left())
        self.assertAlmostEqual((canvas.height() - plate.height()) / 2.0, plate.top())

    def test_portrait_tray_and_workpieces_are_rotated_together_for_display(self) -> None:
        canvas = _PlateCanvas()
        canvas.resize(600, 300)
        plate = canvas._scaled_plate_rect(50.0, 200.0)

        bottom_left = canvas._to_canvas_point(0.0, 0.0, 50.0, 200.0, plate)
        top_left = canvas._to_canvas_point(0.0, 200.0, 50.0, 200.0, plate)
        bottom_right = canvas._to_canvas_point(50.0, 0.0, 50.0, 200.0, plate)

        self.assertAlmostEqual(4.0, plate.width() / plate.height())
        self.assertLess(bottom_left.x(), top_left.x())
        self.assertAlmostEqual(bottom_left.y(), top_left.y())
        self.assertLess(bottom_left.y(), bottom_right.y())

    def test_camera_disabled_uses_expanded_settings_and_tray_tabs(self) -> None:
        view = PaintDashboardView(
            config=PaintDashboardConfig(),
            action_buttons=PAINT_DASHBOARD_ACTIONS,
            cards=[],
            auxiliary_toggles=[],
            ui_config=PaintDashboardUiConfig(show_camera_preview=False),
        )

        self.assertIsNone(view._expanded_tabs)
        preview_container = view._dashboard.layout_manager.main_layout.itemAt(0).layout().itemAt(0).widget()
        self.assertIs(preview_container.layout().itemAt(0).widget(), view._tray_panel)
        self.assertIs(view._plate_layout.parentWidget(), view._tray_panel)
        self.assertFalse(view._plate_layout.isHidden())
        self.assertEqual(view._plate_layout.objectName(), "paintPlateLayout")
        self.assertIn("background-color: white", view._plate_layout.styleSheet())
        self.assertEqual(view._tray_panel.objectName(), "paintTrayPanel")
        self.assertIn("background: white", view._tray_panel.styleSheet())
        self.assertIn("border: 1px solid #E0E0E0", view._tray_panel.styleSheet())
        self.assertEqual(
            view._tray_panel.layout().contentsMargins().left(),
            10,
        )
        self.assertIsNone(view._quick_controls)
        self.assertIsNone(view._controls_drawer)
        self.assertIsNotNone(view._quick_access)
        self.assertTrue(view._plate_layout._new_tray.isHidden())
        top_section = view._dashboard.layout_manager.main_layout.itemAt(0).layout()
        status_column = top_section.itemAt(top_section.count() - 1).widget()
        status_layout = status_column.layout()
        message_host = view._accordion_host
        message_position = status_layout.getItemPosition(
            status_layout.indexOf(message_host)
        )
        self.assertEqual(status_layout.indexOf(view._quick_access), -1)
        self.assertEqual(message_position, (0, 0, 1, 3))
        self.assertGreaterEqual(status_column.minimumWidth(), 650)
        self.assertTrue(view._message_panel.isHidden())
        self.assertIsNotNone(view._message_rail_button)
        self.assertIsNotNone(view._settings_widget)
        self.assertIsNotNone(view._settings_panel)
        self.assertFalse(view._settings_content.isHidden())
        self.assertEqual(
            view._settings_widget._scroll.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertEqual(
            view._settings_widget._scroll.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        for button in view._settings_widget._unmatched_step_buttons:
            self.assertEqual(button.width(), 40)
            self.assertIn(button.text(), {"−", "+"})
            self.assertIn("padding: 0", button.styleSheet())
        self.assertEqual(view._settings_widget._pass_count_box.height(), 104)
        self.assertEqual(view._settings_widget._acceleration_scale_box.height(), 104)
        self.assertTrue(view._settings_widget._acceleration_scale_apply.isHidden())
        self.assertEqual(view._settings_widget._unmatched_apply.text(), "Apply All")
        self.assertIn(
            "border: 1px solid #E0E0E0",
            view._settings_widget._unmatched_velocity.styleSheet(),
        )
        self.assertEqual(view._settings_widget._unmatched_box.title(), "")
        self.assertIsInstance(view._settings_widget._pass_2_use_first, QToggle)
        self.assertEqual(view._settings_widget._pass_2_use_first.height(), 36)
        self.assertEqual(
            view._settings_widget._pass_2_use_first.cursor().shape(),
            Qt.CursorShape.PointingHandCursor,
        )
        self.assertEqual(
            view._settings_widget._pass_1_compact_fields_layout.direction(),
            QVBoxLayout.Direction.TopToBottom,
        )
        painting_requests = []
        scaling_requests = []
        view._settings_widget.unmatched_paint_settings_requested.connect(
            painting_requests.append
        )
        view._settings_widget.acceleration_scale_requested.connect(
            scaling_requests.append
        )
        view._settings_widget._unmatched_apply.click()
        self.assertEqual(len(painting_requests), 1)
        self.assertEqual(scaling_requests, [100.0])
        self.assertEqual(view._settings_title_label.text(), "Settings")
        self.assertTrue(view._settings_title_label.isHidden())
        self.assertIs(view._accordion_layout.itemAt(0).widget(), view._settings_panel)
        self.assertIsNone(view._accordion_layout.itemAt(1).widget())
        self.assertEqual(view._accordion_layout.stretch(0), 1)
        self.assertEqual(view._accordion_layout.stretch(1), 0)
        view._message_rail_button.click()
        self.assertTrue(view._message_drawer_open)
        self.assertFalse(view._message_panel.isHidden())
        view._message_rail_button.click()
        self.assertFalse(view._message_drawer_open)
        view._on_message_drawer_animation_finished()
        self.assertTrue(view._message_panel.isHidden())
        self.assertEqual(
            status_column.sizePolicy().verticalPolicy(),
            QSizePolicy.Policy.Expanding,
        )
        self.assertGreater(status_column.maximumHeight(), 458)
        bottom_container = view._dashboard.layout_manager.main_layout.itemAt(1).widget()
        self.assertEqual(bottom_container.height(), 250)
        bottom_layout = bottom_container.layout()
        quick_controls_host = bottom_layout.itemAt(0).widget()
        process_controls_host = bottom_layout.itemAt(1).widget()
        self.assertIs(
            quick_controls_host.layout().itemAt(0).widget(),
            view._quick_access,
        )
        self.assertEqual(bottom_layout.stretch(0), 1)
        self.assertEqual(bottom_layout.stretch(1), 1)
        self.assertTrue(bottom_layout.contentsMargins().isNull())
        self.assertEqual(bottom_layout.spacing(), 10)
        self.assertTrue(quick_controls_host.layout().contentsMargins().isNull())
        self.assertEqual(view._quick_access._footer_grid.columnCount(), 2)
        self.assertEqual(view._quick_access._box.title(), "")
        footer_buttons = (
            view._quick_access._drying_mode_button,
            *view._quick_access._buttons.values(),
            view._quick_access._cable_relief,
            view._quick_access._new_tray,
        )
        process_buttons = (
            view._dashboard.control_buttons.start_btn,
            view._dashboard.control_buttons.pause_btn,
            view._dashboard._action_buttons["reset_errors"],
            view._dashboard.control_buttons.stop_btn,
        )
        self.assertTrue(all(button.height() == 48 for button in footer_buttons))
        self.assertTrue(all(button.height() == 72 for button in process_buttons))
        for button in process_buttons:
            self.assertEqual(button.color, "#905BA9")
            self.assertIn("background: #905BA9", button.styleSheet())
            self.assertIn("border-radius: 14px", button.styleSheet())
        self.assertEqual(
            view._quick_access._footer_grid.getItemPosition(
                view._quick_access._footer_grid.indexOf(view._quick_access._new_tray)
            ),
            (2, 0, 1, 2),
        )
        self.assertFalse(quick_controls_host.isHidden())
        self.assertIs(process_controls_host, view._process_controls_host)
        reset_button = view._dashboard._action_buttons["reset_errors"]
        control_buttons = view._dashboard.control_buttons
        top_frame = control_buttons.layout().itemAt(0).widget()
        self.assertIs(reset_button.parent(), top_frame)
        self.assertEqual(top_frame.layout().count(), 3)
        self.assertIs(top_frame.layout().itemAt(2).widget(), reset_button)
        for index in range(3):
            button = top_frame.layout().itemAt(index).widget()
            self.assertEqual(
                button.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Ignored,
            )
            self.assertEqual(top_frame.layout().stretch(index), 1)
        bottom_frame = control_buttons.layout().itemAt(1).widget()
        self.assertEqual(bottom_frame.layout().count(), 1)
        self.assertIs(bottom_frame.layout().itemAt(0).widget(), control_buttons.stop_btn)

    def test_camera_disabled_can_keep_settings_in_original_tab(self) -> None:
        view = PaintDashboardView(
            config=PaintDashboardConfig(),
            action_buttons=PAINT_DASHBOARD_ACTIONS,
            cards=[],
            auxiliary_toggles=[],
            ui_config=PaintDashboardUiConfig(
                show_camera_preview=False,
                use_collapsible_settings_panel=False,
            ),
        )

        self.assertEqual(view._expanded_tabs.count(), 2)
        self.assertIs(view._expanded_tabs.widget(0), view._controls_widget)
        self.assertIs(view._expanded_tabs.widget(1), view._plate_layout)
        self.assertEqual(view._expanded_tabs.tabToolTip(0), "Paint Settings")
        self.assertEqual(view._expanded_tabs.tabToolTip(1), "Tray")
        self.assertIsNone(view._settings_widget)
        self.assertIsNone(view._settings_panel)
        self.assertIsNone(view._accordion_layout)
        self.assertTrue(view._message_panel.isHidden())
        self.assertIsNotNone(view._message_rail_button)

    def test_camera_disabled_moves_status_cards_to_exclusive_compact_rail(self) -> None:
        view = PaintDashboardView(
            config=PaintDashboardConfig(),
            action_buttons=PAINT_DASHBOARD_ACTIONS,
            cards=PaintCardFactory().build_cards(PAINT_DASHBOARD_CARDS),
            auxiliary_toggles=[],
            ui_config=PaintDashboardUiConfig(show_camera_preview=False),
        )

        self.assertIsNotNone(view._status_rail)
        rail_layout = view._status_rail.layout()
        self.assertEqual(rail_layout.count(), 6)
        cards = list(view._cards_by_id.values())
        for index, card in enumerate(cards):
            self.assertIs(rail_layout.itemAt(index).widget(), card)
            self.assertEqual(card.width(), 48)
            self.assertFalse(card.is_expanded())
            self.assertFalse(card._indicator.isHidden())
            self.assertEqual(
                card.cursor().shape(),
                Qt.CursorShape.PointingHandCursor,
            )
        self.assertIs(rail_layout.itemAt(4).widget(), view._message_rail_button)

        cards[0].set_expanded(True)
        cards[0].expansion_changed.emit(True)
        self.assertTrue(cards[0].is_expanded())
        self.assertEqual(cards[0].width(), 48)
        self.assertFalse(view._status_flyout.isHidden())
        self.assertEqual(view._status_flyout_title.text(), "Robot Status")
        self.assertEqual(view._status_flyout_note.text(), "Waiting for robot state")
        cards[1].set_expanded(True)
        cards[1].expansion_changed.emit(True)
        self.assertFalse(cards[0].is_expanded())
        self.assertTrue(cards[1].is_expanded())
        self.assertEqual(cards[1].width(), 48)
        self.assertEqual(view._status_flyout_title.text(), "Vision Status")
        cards[1].expansion_changed.emit(False)
        self.assertTrue(view._status_flyout.isHidden())

        cards[0].set_content("Robot Status", "DISCONNECTED", "")
        cards[1].set_content("Vision Status", "ONLINE", "")
        self.assertEqual("#79747E", cards[0]._status_color)
        self.assertEqual("#905BA9", cards[1]._status_color)
        self.assertFalse(cards[0]._indicator.icon().isNull())
        self.assertFalse(cards[1]._indicator.icon().isNull())
        self.assertEqual(cards[0]._icon_name, "mdi.robot-industrial")
        self.assertEqual(cards[1]._icon_name, "fa5s.camera")
        self.assertTrue(cards[2]._icon_name.endswith("assets/paint_process.svg"))
        self.assertTrue(os.path.isfile(cards[2]._icon_name))
        self.assertFalse(cards[2]._indicator.icon().isNull())
        paint_pixmap = cards[2]._indicator.icon().pixmap(32, 32)
        paint_image = paint_pixmap.toImage()
        self.assertTrue(paint_image.hasAlphaChannel())
        self.assertEqual(paint_image.pixelColor(0, 0).alpha(), 0)

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_card_factory_builds_info_cards_with_layout_coordinates(self) -> None:
        cards = PaintCardFactory().build_cards(
            [
                CardConfig(card_id=3, label="Paint", row=1, col=2),
                CardConfig(card_id=4, label="Dry"),
            ]
        )

        self.assertEqual(len(cards), 2)
        self.assertIsInstance(cards[0][0], PaintInfoCard)
        self.assertEqual(cards[0][1:], (3, 1, 2))
        self.assertEqual(cards[1][1:], (4, None, None))

    def test_unmatched_second_pass_tab_defaults_to_pass_one_inheritance(self) -> None:
        drawer = PaintControlsDrawer([])
        drawer.set_unmatched_paint_settings({
            "velocity_percent": 12.0,
            "acceleration_percent": 23.0,
            "offset_mm": -1.0,
            "pass_count": 2,
            "pass_2": {
                "use_pass_1_settings": True,
                "velocity_percent": 34.0,
                "acceleration_percent": 45.0,
                "offset_mm": -2.0,
            },
        })

        self.assertTrue(drawer._unmatched_tabs.isTabVisible(1))
        self.assertTrue(drawer._pass_2_use_first.isChecked())
        self.assertFalse(drawer._pass_2_velocity.isEnabled())
        drawer._pass_2_use_first.setChecked(False)
        self.assertTrue(drawer._pass_2_velocity.isEnabled())
        self.assertEqual(3, len(drawer._pass_2_rows))
        offset_plus = next(
            button for button in drawer._unmatched_step_buttons
            if button.property("field_id") == "pass_2_offset"
            and button.property("step_direction") == 1.0
        )
        offset_plus.click()
        self.assertAlmostEqual(-1.9, drawer._pass_2_offset.value())
        self.assertAlmostEqual(drawer._settings_payload()["pass_2"]["offset_mm"], -1.9)

    def test_info_card_displays_configured_placeholder_content(self) -> None:
        card = PaintInfoCard("Paint", "Running", "Current state")

        self.assertEqual(
            [label.text() for label in card.findChildren(QLabel)],
            ["Paint", "Running"],
        )

    def test_info_card_content_can_be_updated(self) -> None:
        card = PaintInfoCard("Paint", "Running", "Current state")

        card.set_content("Robot Status", "IDLE", "Robot service healthy")

        self.assertEqual(
            [label.text() for label in card.findChildren(QLabel)],
            ["Robot Status", "IDLE"],
        )

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
        calls_after_first_apply = list(view._dashboard.calls)

        view.apply_dashboard_state(state)

        self.assertEqual(view._dashboard.calls, calls_after_first_apply)
        self.assertIsNone(view.clean_up())

    def test_dashboard_view_updates_status_cards_from_state(self) -> None:
        robot_card = MagicMock()
        vision_card = MagicMock()
        state = DashboardState(
            card_states={
                1: DashboardCardState("Robot Status", "IDLE", "Robot service healthy"),
                2: DashboardCardState("Vision Status", "ONLINE", "Vision service healthy"),
            }
        )

        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=[],
                cards=[(robot_card, 1, 0, 0), (vision_card, 2, 1, 0)],
            )

        view.apply_dashboard_state(state)

        robot_card.set_content.assert_called_once_with("Robot Status", "IDLE", "Robot service healthy")
        vision_card.set_content.assert_called_once_with("Vision Status", "ONLINE", "Vision service healthy")

        view.apply_dashboard_state(state)

        robot_card.set_content.assert_called_once()
        vision_card.set_content.assert_called_once()

    def test_view_initialization_tolerates_missing_dashboard_layout(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=2, preview_aux_cols=3),
                action_buttons=[],
                cards=[],
            )

        self.assertIsInstance(view._dashboard, _FakeDashboardWidget)

    def test_controls_drawer_emits_cable_and_data_driven_device_actions(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=[],
                cards=[],
                auxiliary_toggles=[AuxiliaryToggleConfig("fan", "Fan")],
            )

        cable_callback = MagicMock()
        toggle_callback = MagicMock()
        view.cable_relief_requested.connect(cable_callback)
        view.auxiliary_toggle_requested.connect(toggle_callback)

        view._controls_widget._relief_button.click()
        view._controls_widget._buttons["fan"].click()

        cable_callback.assert_called_once_with()
        toggle_callback.assert_called_once_with("fan", True)

    def test_quick_off_command_remains_available_when_device_is_off(self) -> None:
        panel = PaintQuickControlsPanel(
            [AuxiliaryToggleConfig("pump", "Vacuum Pump")]
        )

        panel.set_device_state("pump", False)

        self.assertTrue(panel._off_buttons["pump"].isEnabled())

    def test_press_offset_uses_tenth_millimeter_step(self) -> None:
        panel = PaintQuickControlsPanel([])
        drawer = PaintControlsDrawer([])

        self.assertEqual(panel._offset.singleStep(), 0.1)
        self.assertEqual(drawer._unmatched_offset.singleStep(), 0.1)

    def test_quick_off_command_is_disabled_only_while_command_is_busy(self) -> None:
        panel = PaintQuickControlsPanel(
            [AuxiliaryToggleConfig("fan", "Fan")]
        )

        panel.set_device_state("fan", False)
        panel.set_device_busy("fan", True)
        self.assertFalse(panel._off_buttons["fan"].isEnabled())

        panel.set_device_busy("fan", False)
        self.assertTrue(panel._off_buttons["fan"].isEnabled())

    def test_quick_drying_mode_button_cycles_auto_manual_demo(self) -> None:
        panel = PaintQuickControlsPanel([])
        callback = MagicMock()
        panel.drying_mode_requested.connect(callback)

        panel.set_drying_mode("auto")
        panel._drying_mode_button.click()
        callback.assert_called_once_with("manual")

        callback.reset_mock()
        panel.set_drying_mode("manual")
        panel._drying_mode_button.click()
        callback.assert_called_once_with("demo")

        callback.reset_mock()
        panel.set_drying_mode("demo")
        panel._drying_mode_button.click()
        callback.assert_called_once_with("auto")

    def test_system_ui_config_controls_dashboard_drawer_visibility(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=[],
                cards=[],
                ui_config=PaintDashboardUiConfig(
                    show_jog_widget=False,
                    show_left_drawer=False,
                    show_manual_controls=False,
                ),
            )

        self.assertFalse(view.SHOW_JOG_WIDGET)
        self.assertTrue(view._controls_drawer._btn.isHidden())

    def test_manual_controls_and_shortcuts_are_independently_visible(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=[],
                cards=[],
                ui_config=PaintDashboardUiConfig(
                    show_left_drawer=True,
                    show_manual_controls=False,
                    show_unmatched_paint_controls=False,
                    show_application_shortcuts=True,
                ),
            )

        self.assertTrue(view._controls_widget._unmatched_box.isHidden())

        callback = MagicMock()
        view.application_shortcut_requested.connect(callback)
        view.set_application_shortcuts(
            [
                ApplicationShortcut(
                    "RobotSettings",
                    "RobotSettings",
                    "mdi.robot-industrial",
                    folder_id=2,
                    folder_name="Service",
                    folder_translation_key="folder.service",
                ),
                ApplicationShortcut(
                    "CameraSettings",
                    "CameraSettings",
                    "fa5s.camera",
                    folder_id=2,
                    folder_name="Service",
                    folder_translation_key="folder.service",
                ),
                ApplicationShortcut(
                    "UserManagement",
                    "UserManagement",
                    "fa5s.users-cog",
                    folder_id=3,
                    folder_name="Administration",
                    folder_translation_key="folder.admin",
                ),
            ]
        )
        view._controls_widget._shortcut_buttons["RobotSettings"].click()

        self.assertTrue(view._controls_widget._relief_box.isHidden())
        self.assertTrue(view._controls_widget._devices_box.isHidden())
        self.assertFalse(view._controls_widget._shortcuts_box.isHidden())
        self.assertEqual(view._controls_drawer._content.stretch(0), 1)
        self.assertEqual(view._controls_drawer._content.stretch(1), 0)
        self.assertEqual(len(view._controls_widget._folder_boxes), 2)
        self.assertEqual(
            [box.title() for box in view._controls_widget._folder_boxes],
            ["Service", "Administration"],
        )
        callback.assert_called_once_with("RobotSettings")

    def test_info_and_warning_are_added_to_dashboard_message_queue(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=[],
                cards=[],
            )

            view.show_info("Info", "ok")
            view.show_warning("Warning", "blocked")

        self.assertEqual(len(view._messages), 2)
        self.assertEqual(view._messages[0]["level"], "info")
        self.assertEqual(view._messages[0]["title"], "Info")
        self.assertEqual(view._messages[1]["level"], "warning")
        self.assertEqual(view._messages[1]["message"], "blocked")

    def test_dashboard_message_queue_keeps_latest_fifo_rows(self) -> None:
        with patch(
            "src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view.DashboardWidget",
            _FakeDashboardWidget,
        ):
            view = PaintDashboardView(
                config=SimpleNamespace(preview_aux_rows=1, preview_aux_cols=1),
                action_buttons=[],
                cards=[],
            )

        for index in range(_MAX_MESSAGE_ROWS + 2):
            view.show_warning("Warning", f"message {index}")

        self.assertEqual(len(view._messages), _MAX_MESSAGE_ROWS)
        self.assertEqual(
            [item["message"] for item in view._messages],
            [f"message {index}" for index in range(2, _MAX_MESSAGE_ROWS + 2)],
        )


if __name__ == "__main__":
    unittest.main()
