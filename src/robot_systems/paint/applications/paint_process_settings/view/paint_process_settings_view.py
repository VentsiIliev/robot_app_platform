from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from pl_gui.settings.settings_view.styles import BG_COLOR, LABEL_STYLE
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.keyboard_settings_view import KeyboardSettingsView
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_schema import (
    build_paint_process_settings_tabs,
)


class PaintProcessSettingsView(IApplicationView):
    save_requested = pyqtSignal(dict)

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
        for title, groups in build_paint_process_settings_tabs():
            self.settings_view.add_tab(title, groups)
        self.settings_view.save_requested.connect(self._on_save_requested)
        self._layout.insertWidget(0, self.settings_view)

    def _rebuild_settings_view(self) -> None:
        if self._layout is None or self.settings_view is None:
            return
        old = self.settings_view
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
