from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from pl_gui.settings.settings_view import widget_factory
from pl_gui.settings.settings_view.styles import BG_COLOR, BORDER, GHOST_BTN_STYLE, LABEL_STYLE, TEXT_COLOR
from pl_gui.settings.settings_view.widget_factory import WidgetHandler
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.keyboard_settings_view import KeyboardSettingsView
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_schema import (
    build_paint_process_settings_tabs,
)


class PaintProcessSettingsView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_LIVE_POSITION_ENABLED = True

    save_requested = pyqtSignal(dict)
    value_changed = pyqtSignal(str, object)
    set_safe_travel_current_requested = pyqtSignal()
    set_dropoff_safe_travel_current_requested = pyqtSignal()

    def __init__(self, parent=None):
        self.settings_view: KeyboardSettingsView | None = None
        self._status_label: QLabel | None = None
        self._layout: QVBoxLayout | None = None
        self._current_values: dict = {}
        super().__init__("PaintProcessSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._build_settings_view()
        self._status_label = QLabel()
        self._status_label.setStyleSheet(LABEL_STYLE)
        self._status_label.setContentsMargins(18, 8, 18, 8)
        self._layout.addWidget(self._status_label)
        self.retranslateUi()

    def clean_up(self) -> None:
        pass

    def set_values(self, values: dict) -> None:
        self._current_values = dict(values)
        if self.settings_view is not None:
            self.settings_view.set_values(values)

    def set_safe_travel_position(self, position: list[float]) -> None:
        values = self.values()
        values["safe_travel_position"] = self._format_pose(position)
        self.set_values(values)

    def set_dropoff_safe_travel_position(self, position: list[float]) -> None:
        values = self.values()
        values["dropoff_safe_travel_position"] = self._format_pose(position)
        self.set_values(values)

    def values(self) -> dict:
        if self.settings_view is None:
            return dict(self._current_values)
        return self.settings_view.get_values()

    def set_status(self, message: str) -> None:
        if self._status_label is not None:
            self._status_label.setText(message)

    def retranslateUi(self) -> None:
        if self._status_label is not None and not self._status_label.text():
            self._status_label.setText(self.tr("Changes are applied to the next Paint cycle."))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            values = self.values()
            self._rebuild_settings_view()
            self.set_values(values)
            self.retranslateUi()
            self.language_changed.emit()
        super().changeEvent(event)

    def _build_settings_view(self) -> None:
        if self._layout is None:
            return
        self.settings_view = KeyboardSettingsView(component_name="PaintProcessSettings")
        original_handler = widget_factory._REGISTRY.get("paint_action_button")
        original_pose_handler = widget_factory._REGISTRY.get("paint_pose_display")
        widget_factory._REGISTRY["paint_action_button"] = WidgetHandler(
            create=self._make_action_button,
            get_value=lambda _widget: False,
            set_value=lambda _widget, _value: None,
            full_width=True,
        )
        widget_factory._REGISTRY["paint_pose_display"] = WidgetHandler(
            create=self._make_pose_display,
            get_value=lambda widget: widget.text(),
            set_value=lambda widget, value: widget.setText(str(value or self.tr("Not set"))),
            full_width=True,
        )
        try:
            for title, groups in build_paint_process_settings_tabs():
                self.settings_view.add_tab(title, groups)
        finally:
            if original_handler is None:
                widget_factory._REGISTRY.pop("paint_action_button", None)
            else:
                widget_factory._REGISTRY["paint_action_button"] = original_handler
            if original_pose_handler is None:
                widget_factory._REGISTRY.pop("paint_pose_display", None)
            else:
                widget_factory._REGISTRY["paint_pose_display"] = original_pose_handler
        self.settings_view.value_changed_signal.connect(self._on_value_changed)
        self.settings_view.save_requested.connect(self._on_save_requested)
        self._layout.insertWidget(0, self.settings_view)

    def _make_action_button(self, field, emit):
        button = QPushButton(str(field.default or field.label))
        button.setStyleSheet(GHOST_BTN_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: emit(True))
        return button

    def _make_pose_display(self, field, _emit):
        label = QLabel(str(field.default or self.tr("Not set")))
        label.setWordWrap(True)
        label.setStyleSheet(
            f"""
            QLabel {{
                background: {BG_COLOR};
                color: {TEXT_COLOR};
                border: 2px solid {BORDER};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 11pt;
                min-height: 44px;
            }}
            """
        )
        return label

    def _rebuild_settings_view(self) -> None:
        if self._layout is None or self.settings_view is None:
            return
        old = self.settings_view
        try:
            old.value_changed_signal.disconnect(self._on_value_changed)
        except Exception:
            pass
        try:
            old.save_requested.disconnect(self._on_save_requested)
        except Exception:
            pass
        self._layout.removeWidget(old)
        old.deleteLater()
        self.settings_view = None
        self._build_settings_view()

    def _on_save_requested(self, values: dict) -> None:
        self._current_values = dict(values)
        self.save_requested.emit(values)

    def _on_value_changed(self, key: str, value: object, _component_name: str) -> None:
        if key == "safe_travel_set_current":
            self.set_safe_travel_current_requested.emit()
            return
        if key == "dropoff_safe_travel_set_current":
            self.set_dropoff_safe_travel_current_requested.emit()
            return
        self._current_values = self.values()
        self.value_changed.emit(key, value)

    @staticmethod
    def _format_pose(position: list[float]) -> str:
        return ", ".join(f"{float(value):.3f}" for value in position[:6])
