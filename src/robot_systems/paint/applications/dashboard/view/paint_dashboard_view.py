from __future__ import annotations

from collections import deque
from datetime import datetime

from PyQt6.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.applications.base.i_application_view import IApplicationView
from src.applications.base.styled_message_box import ask_yes_no
from src.applications.base.drawer_toggle import DrawerToggle
from pl_gui.dashboard.DashboardWidget import DashboardWidget
from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    BORDER,
    PRIMARY,
    TAB_WIDGET_STYLE,
    TEXT_COLOR,
)
from pl_gui.shell.ui.icon_loader import load_icon
from src.robot_systems.paint.applications.dashboard.ui.paint_controls_drawer import (
    PaintControlsDrawer,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_quick_controls_panel import (
    PaintQuickControlsPanel,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_plate_layout import PaintPlateLayout
from src.robot_systems.paint.applications.dashboard.ui.paint_quick_access_panel import (
    PaintQuickAccessPanel,
)
from src.robot_systems.paint.applications.dashboard.config import PaintDashboardUiConfig


_MAX_MESSAGE_ROWS = 50
_MESSAGE_SCROLL_MIN_HEIGHT = 60
_CONTROLS_DRAWER_WIDTH = 400
_MESSAGE_DRAWER_HANDLE_CLEARANCE = 38
_PROCESS_CONTROLS_TOP_MARGIN = 19
_PROCESS_CONTROLS_BOTTOM_MARGIN = 5
_EXPANDED_PROCESS_SECTION_HEIGHT = 300
_EXPANDED_STATUS_MIN_WIDTH = 650
_MESSAGE_COLLAPSED_HEIGHT = 45
_SETTINGS_COLLAPSED_HEIGHT = 45
_PROCESS_CONTROLS_PANEL_STYLE = f"""
QFrame#paintProcessControlsPanel {{
    background-color: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
"""
_PROCESS_CONTROLS_CONTENT_STYLE = """
QWidget#paintProcessControls {
    background-color: transparent;
    border: none;
}
"""
_EXPANDED_ICON_TAB_STYLE = TAB_WIDGET_STYLE + """
QTabBar::tab {
    min-width: 72px;
    max-width: 72px;
    min-height: 64px;
    padding: 0;
}
"""
_MESSAGE_PANEL_STYLE = f"""
QFrame {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
"""
_MESSAGE_TITLE_STYLE = f"""
QLabel {{
    color: {TEXT_COLOR};
    font-size: 11pt;
    font-weight: bold;
    background: transparent;
    border: none;
}}
"""
_MESSAGE_EMPTY_STYLE = """
QLabel {
    color: #777777;
    font-size: 10pt;
    background: transparent;
    border: none;
}
"""
_MESSAGE_ROW_STYLE = """
QLabel {
    color: #202124;
    font-size: 10pt;
    background: transparent;
    border: none;
    padding: 2px 0;
}
"""
_MESSAGE_WARNING_STYLE = """
QLabel {
    color: #8A4B00;
    font-size: 10pt;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 2px 0;
}
"""
_MESSAGE_INFO_STYLE = f"""
QLabel {{
    color: {PRIMARY};
    font-size: 10pt;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 2px 0;
}}
"""
_MESSAGE_SCROLL_STYLE = f"""
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: {BG_COLOR};
    width: 24px;
    margin: 0;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QScrollBar::handle:vertical {{
    background: {PRIMARY};
    min-height: 48px;
    border-radius: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical:pressed {{
    background: {PRIMARY};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
    border: none;
    background: transparent;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""


class _ClickableHeader(QWidget):
    clicked = pyqtSignal()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class PaintDashboardView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_DRAWER_SIDE = "right"

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    reset_requested = pyqtSignal()

    action_requested = pyqtSignal(str)
    cable_relief_requested = pyqtSignal()
    auxiliary_toggle_requested = pyqtSignal(str, bool)
    application_shortcut_requested = pyqtSignal(str)
    unmatched_paint_settings_requested = pyqtSignal(object)
    acceleration_scale_requested = pyqtSignal(float)
    drying_mode_requested = pyqtSignal(str)
    new_tray_requested = pyqtSignal()
    remove_plate_placement_requested = pyqtSignal(int)

    def __init__(
        self,
        config,
        action_buttons: list,
        cards: list,
        auxiliary_toggles=None,
        ui_config: PaintDashboardUiConfig | None = None,
        parent=None,
    ):
        self._ui_config = ui_config or PaintDashboardUiConfig()
        self.SHOW_JOG_WIDGET = self._ui_config.show_jog_widget
        self._config = config
        self._action_buttons = action_buttons
        self._cards_input = cards
        self._cards_by_id = self._index_cards_by_id(cards)
        self._last_card_states = {}
        self._last_state_signature = None
        self._messages = deque(maxlen=_MAX_MESSAGE_ROWS)
        self._message_rows: list[QLabel] = []
        self._message_empty_label: QLabel | None = None
        self._message_title_label: QLabel | None = None
        self._message_header: _ClickableHeader | None = None
        self._message_toggle: QToolButton | None = None
        self._message_panel: QFrame | None = None
        self._message_scroll: QScrollArea | None = None
        self._accordion_layout: QVBoxLayout | None = None
        self._settings_widget: PaintControlsDrawer | None = None
        self._settings_panel: QFrame | None = None
        self._settings_content: QWidget | None = None
        self._settings_title_label: QLabel | None = None
        self._settings_toggle: QToolButton | None = None
        self._last_state = None
        self._auxiliary_toggles = list(auxiliary_toggles or [])
        self._controls_drawer = None
        self._controls_widget = None
        self._quick_controls = None
        self._preview_stack = None
        self._plate_layout = None
        self._expanded_tabs = None
        self._quick_access = None
        self._status_rail: QWidget | None = None
        self._status_flyout: QFrame | None = None
        self._status_flyout_title: QLabel | None = None
        self._status_flyout_value: QLabel | None = None
        self._status_flyout_animation: QPropertyAnimation | None = None
        self._active_status_card = None
        super().__init__("PaintDashboard", parent)

    @property
    def action_button_configs(self) -> list:
        return list(self._action_buttons)

    @property
    def application_shortcuts_enabled(self) -> bool:
        return self._ui_config.show_application_shortcuts

    @property
    def shortcut_application_names(self) -> tuple[str, ...]:
        return self._ui_config.shortcut_application_names

    @staticmethod
    def _index_cards_by_id(cards: list) -> dict[int, object]:
        indexed = {}
        for item in cards or []:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            widget, card_id = item[0], item[1]
            indexed[card_id] = widget
        return indexed

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dashboard = DashboardWidget(
            config=self._config,
            action_buttons=self._action_buttons,
            cards=self._cards_input,
        )
        layout.addWidget(self._dashboard)
        self._dashboard.setStyleSheet(f"background-color: {BG_COLOR};")
        self._install_manual_plate_layout()
        self._install_compact_status_rail()
        self._align_preview_and_card_columns()
        self._install_bottom_quick_controls()
        self._install_controls_drawer()
        self._install_message_panel()
        self._place_reset_action()
        self._expand_process_controls()

        self._dashboard.start_requested.connect(self.start_requested)
        self._dashboard.stop_requested.connect(self.stop_requested)
        self._dashboard.pause_requested.connect(self.pause_requested)
        self._dashboard.action_requested.connect(self._on_inner_action)

    def _install_manual_plate_layout(self) -> None:
        try:
            top_section = self._dashboard.layout_manager.main_layout.itemAt(0).layout()
            if top_section is None:
                return
            preview_container = top_section.itemAt(0).widget()
            preview_layout = preview_container.layout()
            camera = self._dashboard.trajectory_widget
            preview_layout.removeWidget(camera)
            self._plate_layout = PaintPlateLayout(
                use_dry_duration=self._ui_config.use_tray_dry_duration,
                drying_duration_minutes=self._ui_config.tray_dry_duration_minutes,
            )
            self._plate_layout.new_tray_requested.connect(self._on_new_tray)
            self._plate_layout.remove_requested.connect(self._on_remove_plate_placement)
            if self._ui_config.show_camera_preview:
                self._preview_stack = QStackedWidget()
                self._preview_stack.addWidget(camera)
                self._preview_stack.addWidget(self._plate_layout)
                preview_layout.insertWidget(0, self._preview_stack)
            else:
                camera.hide()
                self._expanded_tabs = QTabWidget()
                self._expanded_tabs.setStyleSheet(_EXPANDED_ICON_TAB_STYLE)
                self._expanded_tabs.setIconSize(QSize(36, 36))
                self._expanded_tabs.addTab(
                    QWidget(),
                    load_icon("fa5s.sliders-h", color=PRIMARY),
                    "",
                )
                self._expanded_tabs.addTab(
                    self._plate_layout,
                    load_icon("fa5s.th", color=PRIMARY),
                    "",
                )
                self._center_expanded_tab_icon(0, "fa5s.sliders-h")
                self._center_expanded_tab_icon(1, "fa5s.th")
                self._retranslate_expanded_tabs()
                preview_layout.insertWidget(0, self._expanded_tabs)
                self._quick_access = PaintQuickAccessPanel(self._auxiliary_toggles)
                self._quick_access.setMinimumWidth(220)
                self._quick_access.setMaximumWidth(280)
                self._quick_access.device_toggle_requested.connect(
                    self.auxiliary_toggle_requested
                )
                self._quick_access.cable_relief_requested.connect(
                    self.cable_relief_requested
                )
                self._quick_access.drying_mode_requested.connect(
                    self.drying_mode_requested
                )
                self._quick_access.new_tray_requested.connect(self._on_new_tray)
                self._plate_layout.set_new_tray_button_visible(False)
                side_panel = top_section.itemAt(top_section.count() - 1).widget()
                side_layout = side_panel.layout()
                side_layout.addWidget(self._quick_access, 0, 0)
                side_panel.setMinimumWidth(_EXPANDED_STATUS_MIN_WIDTH)
                side_panel.setMaximumWidth(16777215)
        except (AttributeError, RuntimeError):
            self._preview_stack = None
            self._plate_layout = None

    def _install_compact_status_rail(self) -> None:
        if self._ui_config.show_camera_preview:
            return
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            side_panel = top_section.itemAt(top_section.count() - 1).widget()
            side_layout = side_panel.layout()

            rail = QWidget()
            rail.setStyleSheet("background: transparent; border: none;")
            rail_layout = QVBoxLayout(rail)
            rail_layout.setContentsMargins(0, 0, 0, 0)
            rail_layout.setSpacing(6)
            for card in self._cards_by_id.values():
                side_layout.removeWidget(card)
                set_compact = getattr(card, "set_compact", None)
                if callable(set_compact):
                    set_compact(True)
                expanded_changed = getattr(card, "expansion_changed", None)
                if expanded_changed is not None:
                    expanded_changed.connect(self._on_status_card_expansion_changed)
                rail_layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignRight)
            rail_layout.addStretch(1)
            side_layout.addWidget(
                rail,
                0,
                3,
                1,
                1,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
            )
            side_layout.setColumnStretch(3, 0)
            self._status_rail = rail
            self._build_status_flyout(side_panel)
        except (AttributeError, RuntimeError):
            self._status_rail = None

    def _on_status_card_expansion_changed(self, expanded: bool) -> None:
        active_card = self.sender()
        for card in self._cards_by_id.values():
            set_expanded = getattr(card, "set_expanded", None)
            if callable(set_expanded):
                set_expanded(card is active_card and expanded)
        if not expanded:
            self._hide_status_flyout()
            return
        self._active_status_card = active_card
        self._show_status_flyout(active_card)

    def _build_status_flyout(self, parent: QWidget) -> None:
        flyout = QFrame(parent)
        flyout.setStyleSheet(_MESSAGE_PANEL_STYLE)
        flyout.setFixedHeight(76)
        flyout.hide()
        layout = QVBoxLayout(flyout)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        self._status_flyout_title = QLabel()
        self._status_flyout_title.setStyleSheet(_MESSAGE_TITLE_STYLE)
        self._status_flyout_value = QLabel()
        self._status_flyout_value.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 14pt; font-weight: bold; "
            "background: transparent; border: none;"
        )
        layout.addWidget(self._status_flyout_title)
        layout.addWidget(self._status_flyout_value)
        self._status_flyout = flyout
        animation = QPropertyAnimation(flyout, b"geometry", flyout)
        animation.setDuration(240)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._status_flyout_animation = animation

    def _show_status_flyout(self, card) -> None:
        if self._status_flyout is None or self._status_rail is None:
            return
        self._status_flyout_title.setText(card._title_label.text())
        self._status_flyout_value.setText(card._value_label.text())
        rail_top = self._status_rail.mapTo(self._status_flyout.parentWidget(), card.pos())
        right = rail_top.x()
        top = rail_top.y()
        width = 210
        self._status_flyout_animation.stop()
        self._status_flyout.setGeometry(QRect(right, top, 0, 76))
        self._status_flyout.show()
        self._status_flyout.raise_()
        self._status_rail.raise_()
        self._status_flyout_animation.setStartValue(QRect(right, top, 0, 76))
        self._status_flyout_animation.setEndValue(QRect(right - width, top, width, 76))
        self._status_flyout_animation.start()

    def _hide_status_flyout(self) -> None:
        if self._status_flyout is None:
            return
        self._status_flyout_animation.stop()
        self._status_flyout.hide()
        self._active_status_card = None

    def _install_controls_drawer(self) -> None:
        use_panel = (
            not self._ui_config.show_camera_preview
            and self._ui_config.use_collapsible_settings_panel
        )
        self._controls_widget = self._build_controls_widget(concise=use_panel)
        if use_panel:
            self._settings_widget = self._controls_widget
        self._connect_controls_widget(self._controls_widget)
        if self._ui_config.show_camera_preview:
            self._controls_drawer = DrawerToggle(
                self,
                side="left",
                width=_CONTROLS_DRAWER_WIDTH,
            )
            self._controls_drawer.add_widget(self._controls_widget, fill_height=True)
        elif self._expanded_tabs is not None:
            placeholder = self._expanded_tabs.widget(0)
            self._expanded_tabs.removeTab(0)
            placeholder.deleteLater()
            if self._ui_config.use_collapsible_settings_panel:
                self._center_expanded_tab_icon(0, "fa5s.th")
            else:
                self._expanded_tabs.insertTab(
                    0,
                    self._controls_widget,
                    load_icon("fa5s.sliders-h", color=PRIMARY),
                    "",
                )
                self._center_expanded_tab_icon(0, "fa5s.sliders-h")
            self._retranslate_expanded_tabs()
        if self._controls_drawer is not None:
            self._controls_drawer.set_visible(self._ui_config.show_left_drawer)

    def _build_controls_widget(self, *, concise: bool = False) -> PaintControlsDrawer:
        return PaintControlsDrawer(
            self._auxiliary_toggles,
            show_manual_controls=self._ui_config.show_manual_controls,
            show_unmatched_paint_controls=self._ui_config.show_unmatched_paint_controls,
            show_acceleration_scale_control=self._ui_config.show_acceleration_scale_control,
            show_shortcuts=self._ui_config.show_application_shortcuts,
            compact_layout=not self._ui_config.show_camera_preview,
            concise_layout=concise,
            use_combined_speed_control=self._ui_config.use_combined_paint_speed_control,
            combined_speed_minimum_percent=self._ui_config.combined_paint_speed_minimum_percent,
            combined_speed_maximum_percent=self._ui_config.combined_paint_speed_maximum_percent,
            combined_acceleration_minimum_percent=self._ui_config.combined_paint_acceleration_minimum_percent,
            combined_acceleration_maximum_percent=self._ui_config.combined_paint_acceleration_maximum_percent,
            show_resolved_speed_values=self._ui_config.show_resolved_paint_speed_values,
        )

    def _connect_controls_widget(self, widget: PaintControlsDrawer) -> None:
        widget.cable_relief_requested.connect(self.cable_relief_requested)
        widget.device_toggle_requested.connect(self.auxiliary_toggle_requested)
        widget.application_shortcut_requested.connect(
            self.application_shortcut_requested
        )
        widget.unmatched_paint_settings_requested.connect(
            self.unmatched_paint_settings_requested
        )
        widget.acceleration_scale_requested.connect(
            self.acceleration_scale_requested
        )
        widget.drying_mode_requested.connect(self.drying_mode_requested)

    def _install_bottom_quick_controls(self) -> None:
        if (
            not self._ui_config.show_bottom_quick_controls
            or not self._ui_config.show_camera_preview
        ):
            return
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            bottom_container = main_layout.itemAt(1).widget()
            bottom_layout = bottom_container.layout()
            self._quick_controls = PaintQuickControlsPanel(
                self._auxiliary_toggles,
                use_combined_speed_control=(
                    self._ui_config.use_combined_paint_speed_control
                ),
                combined_speed_minimum_percent=(
                    self._ui_config.combined_paint_speed_minimum_percent
                ),
                combined_speed_maximum_percent=(
                    self._ui_config.combined_paint_speed_maximum_percent
                ),
                combined_acceleration_minimum_percent=(
                    self._ui_config.combined_paint_acceleration_minimum_percent
                ),
                combined_acceleration_maximum_percent=(
                    self._ui_config.combined_paint_acceleration_maximum_percent
                ),
                show_resolved_speed_values=(
                    self._ui_config.show_resolved_paint_speed_values
                ),
            )
            top_section = main_layout.itemAt(0).layout()
            side_panel = top_section.itemAt(top_section.count() - 1).widget()
            side_layout = side_panel.layout()
            side_layout.addWidget(self._quick_controls, 1, 0, 1, 3)
            self._quick_controls.unmatched_paint_settings_requested.connect(
                self._on_quick_unmatched_paint_settings
            )
            self._quick_controls.device_off_requested.connect(self._on_quick_device_off)
            self._quick_controls.cable_relief_requested.connect(
                self._on_quick_cable_relief
            )
            self._quick_controls.drying_mode_requested.connect(self.drying_mode_requested)
        except Exception:
            self._quick_controls = None

    def _on_quick_unmatched_paint_settings(
        self,
        settings: dict,
    ) -> None:
        self.unmatched_paint_settings_requested.emit(settings)

    def _on_quick_device_off(self, device_id: str) -> None:
        self.auxiliary_toggle_requested.emit(device_id, False)

    def _on_quick_cable_relief(self) -> None:
        self.cable_relief_requested.emit()

    def _align_preview_and_card_columns(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            preview_container.setStyleSheet(f"background-color: {BG_COLOR};")
            aux_grid = preview_container.layout().itemAt(1).widget()
            aux_grid.setStyleSheet(f"background-color: {BG_COLOR};")
            side_panel = top_section.itemAt(top_section.count() - 1).widget()
            if side_panel is not None:
                side_panel.setStyleSheet(f"background-color: {BG_COLOR};")
                if self._ui_config.show_camera_preview:
                    side_panel.setFixedHeight(
                        int(
                            getattr(
                                self._config,
                                "status_column_height",
                                int(getattr(self._config, "trajectory_height", 450)) + 8,
                            )
                        )
                    )
                    top_section.setAlignment(side_panel, Qt.AlignmentFlag.AlignTop)
                else:
                    policy = side_panel.sizePolicy()
                    policy.setVerticalPolicy(QSizePolicy.Policy.Expanding)
                    side_panel.setSizePolicy(policy)
        except Exception:
            pass

    def _install_message_panel(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            preview_container = top_section.itemAt(0).widget()
            aux_grid = preview_container.layout().itemAt(1).widget()
            self._clear_layout(aux_grid.layout())
            aux_grid.hide()
            side_panel = top_section.itemAt(top_section.count() - 1).widget()
            layout = side_panel.layout()
            if layout is None:
                return
            panel = self._build_message_panel()
            panel_host = QWidget()
            panel_host.setStyleSheet("background: transparent; border: none;")
            panel_host_layout = QHBoxLayout(panel_host)
            panel_host_layout.setContentsMargins(
                0,
                0,
                0 if self._status_rail is not None else _MESSAGE_DRAWER_HANDLE_CLEARANCE,
                0,
            )
            panel_host_layout.addWidget(panel, alignment=Qt.AlignmentFlag.AlignTop)
            self._message_panel = panel
            if self._quick_access is not None and self._settings_widget is not None:
                message_row = 0
                accordion = QWidget()
                accordion.setStyleSheet("background: transparent; border: none;")
                accordion_layout = QVBoxLayout(accordion)
                accordion_layout.setContentsMargins(
                    0,
                    0,
                    0,
                    0,
                )
                accordion_layout.setSpacing(8)
                panel_host_layout.setContentsMargins(0, 0, 0, 0)
                panel_host_layout.removeWidget(panel)
                panel.setParent(accordion)
                settings_panel = self._build_settings_panel()
                accordion_layout.addWidget(settings_panel, 1)
                accordion_layout.addWidget(panel, 0)
                accordion_layout.addStretch(0)
                layout.addWidget(accordion, message_row, 1, 1, 2)
                self._accordion_layout = accordion_layout
                self._settings_panel = settings_panel
                self._set_message_collapsed(True)
                self._set_settings_collapsed(False)
            elif self._quick_access is not None:
                message_row = 0
                layout.addWidget(panel_host, message_row, 1, 1, 2)
            else:
                message_row = 2
                layout.addWidget(panel_host, message_row, 0, 1, 3)
            layout.setRowMinimumHeight(0, 0 if self._status_rail is not None else 82)
            layout.setRowStretch(0, 0)
            layout.setRowStretch(1, int(message_row == 1))
            layout.setRowStretch(message_row, 1)
            for column in range(3):
                layout.setColumnStretch(column, 1)
            self._render_messages()
        except Exception:
            pass

    def _build_message_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(_MESSAGE_PANEL_STYLE)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        header = _ClickableHeader()
        header.setStyleSheet("background: transparent; border: none;")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.clicked.connect(self._toggle_message_panel)
        self._message_header = header
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self._message_title_label = QLabel()
        self._message_title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self._message_title_label.setStyleSheet(_MESSAGE_TITLE_STYLE)
        header_layout.addWidget(self._message_title_label)
        header_layout.addStretch(1)

        self._message_toggle = QToolButton()
        self._message_toggle.setAutoRaise(True)
        self._message_toggle.setIconSize(QSize(18, 18))
        self._message_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._message_toggle.setFixedSize(32, 28)
        self._message_toggle.setStyleSheet(
            f"QToolButton {{ color: {PRIMARY}; background: transparent; border: none; }}"
            f"QToolButton:hover {{ background: {BG_COLOR}; border-radius: 6px; }}"
        )
        self._message_toggle.clicked.connect(self._toggle_message_panel)
        header_layout.addWidget(self._message_toggle)
        layout.addWidget(header)

        self._message_scroll = QScrollArea()
        self._message_scroll.setWidgetResizable(True)
        self._message_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._message_scroll.setMinimumHeight(_MESSAGE_SCROLL_MIN_HEIGHT)
        self._message_scroll.setStyleSheet(_MESSAGE_SCROLL_STYLE)

        rows_container = QWidget()
        rows_container.setStyleSheet("background: transparent; border: none;")
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(0)

        self._message_empty_label = QLabel()
        self._message_empty_label.setStyleSheet(_MESSAGE_EMPTY_STYLE)
        rows_layout.addWidget(self._message_empty_label)

        self._message_rows = []
        for _index in range(_MAX_MESSAGE_ROWS):
            row = QLabel("")
            row.setWordWrap(True)
            row.setStyleSheet(_MESSAGE_ROW_STYLE)
            row.hide()
            rows_layout.addWidget(row)
            self._message_rows.append(row)

        rows_layout.addStretch(1)
        self._message_scroll.setWidget(rows_container)
        layout.addWidget(self._message_scroll, 1)
        self.retranslateUi()
        return panel

    def _build_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(_MESSAGE_PANEL_STYLE)
        panel.setMaximumHeight(_SETTINGS_COLLAPSED_HEIGHT)
        policy = panel.sizePolicy()
        policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
        panel.setSizePolicy(policy)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        header = _ClickableHeader()
        header.setStyleSheet("background: transparent; border: none;")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.clicked.connect(self._toggle_settings_panel)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self._settings_title_label = QLabel()
        self._settings_title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self._settings_title_label.setStyleSheet(_MESSAGE_TITLE_STYLE)
        self._settings_title_label.setText(self._translate_text("Settings"))
        header_layout.addWidget(self._settings_title_label)
        header_layout.addStretch(1)

        self._settings_toggle = QToolButton()
        self._settings_toggle.setAutoRaise(True)
        self._settings_toggle.setIconSize(QSize(18, 18))
        self._settings_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_toggle.setFixedSize(32, 28)
        self._settings_toggle.setStyleSheet(
            f"QToolButton {{ color: {PRIMARY}; background: transparent; border: none; }}"
            f"QToolButton:hover {{ background: {BG_COLOR}; border-radius: 6px; }}"
        )
        self._settings_toggle.clicked.connect(self._toggle_settings_panel)
        header_layout.addWidget(self._settings_toggle)
        layout.addWidget(header)

        self._settings_content = self._settings_widget
        if self._settings_content is not None:
            self._settings_content.hide()
            layout.addWidget(self._settings_content, 1)
        self._retranslate_settings_toggle(True)
        return panel

    def _toggle_message_panel(self) -> None:
        if self._message_panel is None or self._message_scroll is None:
            return
        collapsed = not self._message_scroll.isHidden()
        if not collapsed:
            self._set_settings_collapsed(True)
        self._set_message_collapsed(collapsed)

    def _set_message_collapsed(self, collapsed: bool) -> None:
        if self._message_panel is None or self._message_scroll is None:
            return
        self._message_scroll.setVisible(not collapsed)
        if collapsed:
            self._message_panel.setMaximumHeight(_MESSAGE_COLLAPSED_HEIGHT)
            vertical_policy = QSizePolicy.Policy.Fixed
        else:
            self._message_panel.setMaximumHeight(16777215)
            vertical_policy = QSizePolicy.Policy.Expanding
        policy = self._message_panel.sizePolicy()
        policy.setVerticalPolicy(vertical_policy)
        self._message_panel.setSizePolicy(policy)
        self._retranslate_message_toggle(collapsed)
        self._update_accordion_stretch()

    def _toggle_settings_panel(self) -> None:
        if self._settings_content is None:
            return
        collapsed = not self._settings_content.isHidden()
        if not collapsed:
            self._set_message_collapsed(True)
        self._set_settings_collapsed(collapsed)

    def _set_settings_collapsed(self, collapsed: bool) -> None:
        if self._settings_panel is None or self._settings_content is None:
            return
        self._settings_content.setVisible(not collapsed)
        self._settings_panel.setMaximumHeight(
            _SETTINGS_COLLAPSED_HEIGHT if collapsed else 16777215
        )
        policy = self._settings_panel.sizePolicy()
        policy.setVerticalPolicy(
            QSizePolicy.Policy.Fixed if collapsed else QSizePolicy.Policy.Expanding
        )
        self._settings_panel.setSizePolicy(policy)
        self._retranslate_settings_toggle(collapsed)
        self._update_accordion_stretch()

    def _update_accordion_stretch(self) -> None:
        if self._accordion_layout is None:
            return
        message_expanded = bool(
            self._message_scroll is not None and not self._message_scroll.isHidden()
        )
        settings_expanded = bool(
            self._settings_content is not None and not self._settings_content.isHidden()
        )
        self._accordion_layout.setStretch(0, int(settings_expanded))
        self._accordion_layout.setStretch(1, int(message_expanded))
        self._accordion_layout.setStretch(
            2,
            int(not settings_expanded and not message_expanded),
        )

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _place_reset_action(self) -> None:
        try:
            reset_button = self._dashboard._action_buttons.get("reset_errors")
            if reset_button is None:
                return
            if self._quick_access is not None:
                controls = self._dashboard.control_buttons
                top_frame = controls.layout().itemAt(0).widget()
                top_layout = top_frame.layout()
                top_layout.addWidget(reset_button)
                for index, button in enumerate(
                    (controls.start_btn, controls.pause_btn, reset_button)
                ):
                    policy = button.sizePolicy()
                    policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                    button.setSizePolicy(policy)
                    top_layout.setStretch(index, 1)
                return
            reset_button.setFixedHeight(52)
            main_layout = self._dashboard.layout_manager.main_layout
            top_section = main_layout.itemAt(0).layout()
            side_panel = top_section.itemAt(top_section.count() - 1).widget()
            side_layout = side_panel.layout()
            side_layout.addWidget(reset_button, 3, 0, 1, 3)
        except Exception:
            pass

    def _expand_process_controls(self) -> None:
        try:
            main_layout = self._dashboard.layout_manager.main_layout
            bottom_container = main_layout.itemAt(1).widget()
            if not self._ui_config.show_camera_preview:
                bottom_container.setFixedHeight(_EXPANDED_PROCESS_SECTION_HEIGHT)
            bottom_layout = bottom_container.layout()
            action_area = bottom_layout.itemAt(0).widget()
            controls = bottom_layout.itemAt(1).widget()
            controls = self._wrap_process_controls(bottom_layout, controls)
            action_area.hide()
            bottom_layout.setStretchFactor(action_area, 0)
            bottom_layout.setStretchFactor(controls, 1)
        except Exception:
            pass

    def _wrap_process_controls(self, bottom_layout, controls: QWidget) -> QWidget:
        """Give the process controls their own card, independent of inherited styles."""
        host = QWidget()
        host.setStyleSheet("background-color: transparent;")
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(
            0,
            _PROCESS_CONTROLS_TOP_MARGIN,
            0,
            _PROCESS_CONTROLS_BOTTOM_MARGIN,
        )
        host_layout.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("paintProcessControlsPanel")
        panel.setStyleSheet(_PROCESS_CONTROLS_PANEL_STYLE)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(5, 5, 5, 5)
        panel_layout.setSpacing(0)

        bottom_layout.replaceWidget(controls, host)
        controls.setObjectName("paintProcessControls")
        controls.setStyleSheet(_PROCESS_CONTROLS_CONTENT_STYLE)
        panel_layout.addWidget(controls)
        host_layout.addWidget(panel)
        self._process_controls_host = host
        self._process_controls_panel = panel
        return host

    def _on_inner_action(self, action_id: str) -> None:
        if action_id == "reset_errors":
            self.reset_requested.emit()
            return
        self.action_requested.emit(action_id)

    def set_trajectory_image(self, image) -> None:
        self._dashboard.set_trajectory_image(image)

    def set_state(self, state: str) -> None:
        _ = state

    def set_mode(self, mode: str) -> None:
        _ = mode

    def set_active_job(self, label: str) -> None:
        _ = label

    def set_notes(self, lines: list[str]) -> None:
        _ = lines

    def set_start_enabled(self, enabled: bool) -> None:
        self._dashboard.set_start_enabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self._dashboard.set_stop_enabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self._dashboard.set_pause_enabled(enabled)

    def set_pause_label(self, text: str) -> None:
        self._dashboard.set_pause_text(self._translate_text(text))

    def set_action_enabled(self, action_id: str, enabled: bool) -> None:
        self._dashboard.set_action_button_enabled(action_id, enabled)

    def set_action_button_text(self, action_id: str, text: str) -> None:
        self._dashboard.set_action_button_text(action_id, self._translate_text(text))

    def set_auxiliary_state(self, device_id: str, enabled: bool) -> None:
        for widget in self._control_widgets():
            widget.set_device_state(device_id, enabled)
        if self._quick_controls is not None:
            self._quick_controls.set_device_state(device_id, enabled)
        if self._quick_access is not None:
            self._quick_access.set_device_state(device_id, enabled)

    def set_auxiliary_busy(self, device_id: str, busy: bool) -> None:
        for widget in self._control_widgets():
            widget.set_device_busy(device_id, busy)
        if self._quick_controls is not None:
            self._quick_controls.set_device_busy(device_id, busy)
        if self._quick_access is not None:
            self._quick_access.set_device_busy(device_id, busy)

    def set_cable_relief_busy(self, busy: bool) -> None:
        for widget in self._control_widgets():
            widget.set_cable_relief_busy(busy)
        if self._quick_controls is not None:
            self._quick_controls.set_cable_relief_busy(busy)
        if self._quick_access is not None:
            self._quick_access.set_cable_relief_busy(busy)

    def set_drying_mode(self, mode: str) -> None:
        if self._quick_controls is not None:
            self._quick_controls.set_drying_mode(mode)
        if self._preview_stack is not None:
            self._preview_stack.setCurrentIndex(1 if str(mode).lower() == "manual" else 0)
        for widget in self._control_widgets():
            widget.set_drying_mode(mode)
        if self._quick_access is not None:
            self._quick_access.set_drying_mode(mode)

    def set_plate_layout_state(self, state: dict[str, object]) -> None:
        if self._plate_layout is not None:
            self._plate_layout.set_state(state)

    def _on_new_tray(self) -> None:
        if ask_yes_no(
            self,
            self._translate_text("New Tray"),
            self._translate_text("Clear all workpieces and start a new tray?"),
            default_no=True,
        ):
            self.new_tray_requested.emit()

    def _on_remove_plate_placement(self, placement_id: int) -> None:
        if ask_yes_no(
            self,
            self._translate_text("Remove Workpiece"),
            self._translate_text("Remove the selected workpiece from the tray?"),
            default_no=True,
        ):
            self.remove_plate_placement_requested.emit(placement_id)

    def clear_plate_selection(self) -> None:
        if self._plate_layout is not None:
            self._plate_layout.clear_selection()

    def set_drying_mode_busy(self, busy: bool) -> None:
        if self._quick_controls is not None:
            self._quick_controls.set_drying_mode_busy(busy)
        for widget in self._control_widgets():
            widget.set_drying_mode_busy(busy)
        if self._quick_access is not None:
            self._quick_access.set_drying_mode_busy(busy)

    def ask_enable_dryer(self, title: str, message: str) -> bool:
        return ask_yes_no(self, title, message, default_no=True)

    def ask_run_without_dryer(self, title: str, message: str) -> bool:
        return ask_yes_no(self, title, message, default_no=True)

    def set_application_shortcuts(self, shortcuts: list) -> None:
        for widget in self._control_widgets():
            widget.set_application_shortcuts(shortcuts)

    def set_unmatched_paint_settings(self, settings: dict) -> None:
        for widget in self._control_widgets():
            widget.set_unmatched_paint_settings(settings)
        if self._quick_controls is not None:
            self._quick_controls.set_unmatched_paint_settings(settings)

    def set_unmatched_paint_settings_editable(self, editable: bool) -> None:
        for widget in self._control_widgets():
            widget.set_unmatched_paint_settings_editable(editable)
        if self._quick_controls is not None:
            self._quick_controls.set_settings_editable(editable)

    def set_acceleration_scale(self, value: float) -> None:
        for widget in self._control_widgets():
            widget.set_acceleration_scale(value)

    def set_acceleration_scale_editable(self, editable: bool) -> None:
        for widget in self._control_widgets():
            widget.set_acceleration_scale_editable(editable)

    def _control_widgets(self) -> tuple[PaintControlsDrawer, ...]:
        if self._controls_widget is None:
            return ()
        return (self._controls_widget,)

    def show_info(self, title: str, message: str) -> None:
        self._enqueue_message("info", title, message)

    def show_warning(self, title: str, message: str) -> None:
        self._enqueue_message("warning", title, message)

    def _enqueue_message(self, level: str, title: str, message: str) -> None:
        clean_title = str(title or "").strip()
        clean_message = str(message or "").strip()
        if not clean_title and not clean_message:
            return
        self._messages.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": str(level or "info").strip().lower(),
                "title": clean_title,
                "message": clean_message,
            }
        )
        self._render_messages()

    def _render_messages(self) -> None:
        if self._message_empty_label is None or not self._message_rows:
            return

        messages = list(self._messages)
        self._message_empty_label.setVisible(not messages)
        for index, row in enumerate(self._message_rows):
            if index >= len(messages):
                row.clear()
                row.hide()
                continue
            item = messages[index]
            row.setText(self._format_message(item))
            row.setStyleSheet(
                _MESSAGE_WARNING_STYLE
                if item["level"] == "warning"
                else _MESSAGE_INFO_STYLE
                if item["level"] == "info"
                else _MESSAGE_ROW_STYLE
            )
            row.show()

        QTimer.singleShot(0, self._scroll_messages_to_bottom)

    def _scroll_messages_to_bottom(self) -> None:
        if self._message_scroll is None:
            return
        bar = self._message_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _format_message(self, item: dict) -> str:
        title = str(item.get("title") or "").strip()
        message = str(item.get("message") or "").strip()
        title = self._translate_text(title)
        message = self._translate_text(message)
        if title and message:
            body = f"{title}: {message}"
        else:
            body = title or message
        return f"{item.get('time', '')}  {body}".strip()

    def show_debug_plot(self, title: str, image_path: str, message: str = "") -> None:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.show_warning(title, self._translate_template("Could not load plot image:\n{image_path}", image_path=image_path))
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(self._translate_text(title))
        dialog.resize(1200, 800)

        layout = QVBoxLayout(dialog)
        if message:
            message_label = QLabel(self._translate_text(message))
            message_label.setWordWrap(True)
            layout.addWidget(message_label)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setPixmap(pixmap)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(image_label)
        layout.addWidget(scroll, 1)

        dialog.exec()

    def apply_dashboard_state(self, state) -> None:
        self._last_state = state
        signature = self._state_signature(state)
        if self._last_state_signature == signature:
            return
        self._last_state_signature = signature
        self.set_state(state.process_state)
        self.set_mode(state.mode_label)
        self.set_active_job(state.active_job_label)
        self.set_notes(state.status_lines)
        self._apply_card_states(getattr(state, "card_states", {}))
        self.set_start_enabled(state.can_start)
        self.set_stop_enabled(state.can_stop)
        self.set_pause_enabled(state.can_pause)
        self.set_pause_label(state.pause_label)
        self.set_action_enabled("reset_errors", state.process_state == "error")
        settings_editable = (
            self._ui_config.allow_running_paint_settings_updates
            or state.process_state in ("idle", "stopped", "error")
        )
        self.set_unmatched_paint_settings_editable(settings_editable)
        self.set_acceleration_scale_editable(settings_editable)
        if self._plate_layout is not None:
            tray_editable = state.process_state in ("idle", "stopped", "error")
            self._plate_layout.set_editable(
                tray_editable,
                removal_editable=True,
            )
            if self._quick_access is not None:
                self._quick_access.set_new_tray_enabled(tray_editable)

    @staticmethod
    def _state_signature(state) -> tuple:
        card_states = getattr(state, "card_states", {}) or {}
        return (
            getattr(state, "process_state", None),
            getattr(state, "mode_label", None),
            getattr(state, "active_job_label", None),
            tuple(getattr(state, "status_lines", []) or []),
            tuple(
                sorted(
                    (
                        card_id,
                        getattr(card_state, "title", ""),
                        getattr(card_state, "value", ""),
                        getattr(card_state, "note", ""),
                    )
                    for card_id, card_state in card_states.items()
                )
            ),
            getattr(state, "can_start", None),
            getattr(state, "can_stop", None),
            getattr(state, "can_pause", None),
            getattr(state, "pause_label", None),
        )

    def _apply_card_states(self, card_states: dict) -> None:
        for card_id, card_state in (card_states or {}).items():
            if self._last_card_states.get(card_id) == card_state:
                continue
            card = self._cards_by_id.get(card_id)
            set_content = getattr(card, "set_content", None)
            if not callable(set_content):
                continue
            set_content(
                self._translate_text(getattr(card_state, "title", "")),
                self._translate_text(getattr(card_state, "value", "")),
                self._translate_text(getattr(card_state, "note", "")),
            )
            set_status_value = getattr(card, "set_status_value", None)
            if callable(set_status_value):
                set_status_value(getattr(card_state, "value", ""))
            if card is self._active_status_card:
                self._status_flyout_title.setText(card._title_label.text())
                self._status_flyout_value.setText(card._value_label.text())
            self._last_card_states[card_id] = card_state

    def retranslateUi(self) -> None:
        if hasattr(self, "_dashboard"):
            self._dashboard.retranslateUi()
            for action in self._action_buttons:
                self.set_action_button_text(action.action_id, action.label)
        if self._message_title_label is not None:
            self._message_title_label.setText(self._translate_text("Messages"))
        if self._message_toggle is not None:
            self._retranslate_message_toggle(
                self._message_scroll is not None and self._message_scroll.isHidden()
            )
        if self._message_empty_label is not None:
            self._message_empty_label.setText(self._translate_text("No process messages"))
        if self._settings_title_label is not None:
            self._settings_title_label.setText(self._translate_text("Settings"))
        if self._settings_toggle is not None:
            self._retranslate_settings_toggle(
                self._settings_content is None or self._settings_content.isHidden()
            )
        for widget in self._control_widgets():
            widget.retranslateUi()
        if self._quick_controls is not None:
            self._quick_controls.retranslateUi()
        if self._quick_access is not None:
            self._quick_access.retranslateUi()
        if self._expanded_tabs is not None:
            self._retranslate_expanded_tabs()
        self._last_card_states.clear()
        self._last_state_signature = None
        if self._last_state is not None:
            self.apply_dashboard_state(self._last_state)
        self._render_messages()

    def _retranslate_message_toggle(self, collapsed: bool) -> None:
        if self._message_toggle is None:
            return
        source = "Expand Messages" if collapsed else "Collapse Messages"
        text = self._translate_text(source)
        self._message_toggle.setToolTip(text)
        self._message_toggle.setAccessibleName(text)
        icon_name = "fa5s.chevron-right" if collapsed else "fa5s.chevron-down"
        self._message_toggle.setIcon(load_icon(icon_name, color=PRIMARY))

    def _retranslate_settings_toggle(self, collapsed: bool) -> None:
        if self._settings_toggle is None:
            return
        source = "Expand Settings" if collapsed else "Collapse Settings"
        text = self._translate_text(source)
        self._settings_toggle.setToolTip(text)
        self._settings_toggle.setAccessibleName(text)
        icon_name = "fa5s.chevron-right" if collapsed else "fa5s.chevron-down"
        self._settings_toggle.setIcon(load_icon(icon_name, color=PRIMARY))

    def _retranslate_expanded_tabs(self) -> None:
        if self._expanded_tabs is None:
            return
        if self._ui_config.use_collapsible_settings_panel:
            labels = (self._translate_text("Tray"),)
        else:
            labels = (
                self._translate_text("Paint Settings"),
                self._translate_text("Tray"),
            )
        for index, label in enumerate(labels):
            self._expanded_tabs.setTabText(index, "")
            self._expanded_tabs.setTabToolTip(index, label)
            self._expanded_tabs.widget(index).setAccessibleName(label)

    def _center_expanded_tab_icon(self, index: int, icon_name: str) -> None:
        if self._expanded_tabs is None:
            return
        icon_label = QLabel(self._expanded_tabs.tabBar())
        icon_label.setFixedSize(72, 64)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setPixmap(load_icon(icon_name, color=PRIMARY).pixmap(QSize(36, 36)))
        self._expanded_tabs.setTabIcon(index, QIcon())
        self._expanded_tabs.tabBar().setTabButton(
            index,
            QTabBar.ButtonPosition.LeftSide,
            icon_label,
        )

    @staticmethod
    def _translate_text(text: str) -> str:
        source = str(text or "")
        translated = QCoreApplication.translate("PaintDashboard", source)
        if translated:
            return translated
        dynamic = PaintDashboardView._translate_dynamic_text(source)
        return dynamic or source

    @staticmethod
    def _translate_dynamic_text(text: str) -> str:
        if text.startswith("Cable relief failed: "):
            error = text.removeprefix("Cable relief failed: ")
            template = QCoreApplication.translate(
                "PaintDashboard", "Cable relief failed: {error}"
            ) or "Cable relief failed: {error}"
            return template.format(error=error)
        if text.startswith("Could not switch ") and ": " in text:
            device, error = text.removeprefix("Could not switch ").split(": ", 1)
            template = QCoreApplication.translate(
                "PaintDashboard", "Could not switch {device}: {error}"
            ) or "Could not switch {device}: {error}"
            return template.format(device=device, error=error)
        templates = (
            ("Runtime startup phase: ", "Runtime startup phase: {phase}", "phase"),
            ("Drive state: ", "Drive state: {state}", "state"),
            ("Could not read vision state: ", "Could not read vision state: {error}", "error"),
            ("Failed to transform latest contour: ", "Failed to transform latest contour: {error}", "error"),
            ("Failed to create contour transform plot: ", "Failed to create contour transform plot: {error}", "error"),
            ("Could not save unmatched paint settings: ", "Could not save unmatched paint settings: {error}", "error"),
            ("Saved contour transform debug plot to ", "Saved contour transform debug plot to {image_path}", "image_path"),
        )
        for prefix, template, field in templates:
            if text.startswith(prefix):
                value = text[len(prefix):]
                translated = QCoreApplication.translate("PaintDashboard", template) or template
                return translated.format(**{field: value})
        return ""

    @staticmethod
    def _translate_template(template: str, **values) -> str:
        translated = QCoreApplication.translate("PaintDashboard", template) or template
        return translated.format(**values)

    def clean_up(self) -> None:
        pass
