from typing import Callable, List

from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QWidget, QTabBar, QTabWidget,
    QVBoxLayout, QScrollArea, QPushButton
)
from PyQt6.QtCore import QCoreApplication, QEvent, QRectF, QSize, pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPainter, QPen

from pl_gui.settings.settings_view.schema import SettingGroup
from pl_gui.settings.settings_view.group_widget import GenericSettingGroup
from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    PRIMARY,
    SECONDARY_BG,
    SAVE_BUTTON_STYLE,
    SETTINGS_CARD_FRAME_STYLE,
    SETTINGS_CARD_BODY_STYLE,
    SETTINGS_FOOTER_STYLE,
    SETTINGS_FIELD_LABEL_STYLE,
    SETTINGS_HEADER_STYLE,
    SETTINGS_STEP_STYLE,
    STATUS_OK,
    TEXT_COLOR,
    TOUCH_SCROLL_AREA_STYLE,
)


class _SettingsTabBar(QTabBar):
    """Paint one segmented tab control without native tab overlap."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setMouseTracking(True)
        self._hovered = -1
        font = self.font()
        font.setPointSize(11)
        font.setBold(True)
        self.setFont(font)

    def tabSizeHint(self, index: int) -> QSize:
        width = max(90, self.fontMetrics().horizontalAdvance(self.tabText(index)) + 44)
        return QSize(width + (16 if index == 0 else 0), 56)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(16, 0, self.width() - 17, self.height() - 1)
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("white"))
        painter.drawRoundedRect(outer, 14, 14)
        for index in range(self.count()):
            rect = QRectF(self.tabRect(index))
            if index == 0:
                rect.setLeft(rect.left() + 16)
            rect.adjust(4, 4, -4, -4)
            selected = index == self.currentIndex()
            hovered = index == self._hovered
            if selected or hovered:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(PRIMARY if selected else SECONDARY_BG))
                painter.drawRoundedRect(rect, 10, 10)
            painter.setPen(QColor("white" if selected else TEXT_COLOR))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.tabText(index))

    def mouseMoveEvent(self, event) -> None:
        hovered = self.tabAt(event.pos())
        if hovered != self._hovered:
            self._hovered = hovered
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = -1
        self.update()
        super().leaveEvent(event)


class SettingsView(QWidget):
    """
    Schema-driven settings UI — touch-friendly.

    Usage:
        view = SettingsView("RobotSettings")
        view.add_tab("General", [ROBOT_INFO_GROUP, GLOBAL_MOTION_GROUP])
        view.add_tab("Safety",  [SAFETY_LIMITS_GROUP])
        view.set_values(flat_dict)
        view.value_changed_signal.connect(handler)
        view.save_requested.connect(on_save)
    """

    value_changed_signal = pyqtSignal(str, object, str)  # key, value, component_name
    save_requested = pyqtSignal(dict)                     # emits current values on Save
    discard_requested = pyqtSignal()

    def __init__(self, component_name: str = "SettingsView", mapper=None, parent: QWidget = None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._component_name = component_name
        self._mapper = mapper
        self._groups: List[GenericSettingGroup] = []
        self._section_headers: list[tuple[QLabel, str]] = []
        self._step_labels: list[QLabel] = []
        self._cached_values: dict = {}
        self._lazy_tab_builders: dict[int, Callable[[], None]] = {}

        self._tabs = QTabWidget()
        self._tabs.setTabBar(_SettingsTabBar())
        self._tabs.setStyleSheet(f"QTabWidget::pane {{ border: none; background: {BG_COLOR}; }}")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._request_save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._page_header = QLabel()
        self._page_header.setObjectName("settingsHeader")
        self._page_header.setStyleSheet(SETTINGS_HEADER_STYLE)
        layout.addWidget(self._page_header)
        layout.addSpacing(12)
        layout.addWidget(self._tabs)

        footer = QWidget()
        footer.setObjectName("settingsFooter")
        footer.setStyleSheet(SETTINGS_FOOTER_STYLE)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        self._footer_layout = footer_layout
        self._status_dot = QFrame()
        self._status_dot.setFixedSize(10, 10)
        footer_layout.addWidget(self._status_dot)
        self._status_label = QLabel()
        self._status_label.setStyleSheet(f"color: {STATUS_OK}; background: transparent; font-size: 10pt;")
        footer_layout.addWidget(self._status_label)
        footer_layout.addStretch()
        self._discard_btn = QPushButton()
        self._discard_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._discard_btn.clicked.connect(self._request_discard)
        footer_layout.addWidget(self._discard_btn)
        footer_layout.addWidget(self._save_btn)
        layout.addWidget(footer)
        self._change_controls_enabled = False
        self._dirty = False
        self._status_label.hide()
        self._status_dot.hide()
        self._discard_btn.hide()
        self.retranslateUi()

    def enable_change_controls(self) -> None:
        self._change_controls_enabled = True
        self._status_label.show()
        self._status_dot.show()
        self._discard_btn.show()
        self.set_dirty(False)

    def set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        if self._change_controls_enabled:
            self._discard_btn.setEnabled(dirty)
            self._save_btn.setEnabled(dirty)
            self.retranslateUi()

    def retranslateUi(self) -> None:
        self._page_header.setText(self.tr("SETTINGS") or "SETTINGS")
        self._save_btn.setText(self.tr("Save") or "Save")
        self._discard_btn.setText(self.tr("Discard") or "Discard")
        self._status_label.setText(
            (self.tr("Unsaved changes") or "Unsaved changes") if self._dirty
            else (self.tr("All changes saved") or "All changes saved")
        )
        color = PRIMARY if self._dirty else STATUS_OK
        self._status_label.setStyleSheet(f"color: {color}; background: transparent; font-size: 10pt;")
        self._status_dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        for header, source in self._section_headers:
            header.setText(self._translate_title(source).upper())
        for label in self._step_labels:
            label.setText(self.tr("STEP") or "STEP")

    def _translate_title(self, source: str) -> str:
        return QCoreApplication.translate(self._component_name, source) or source

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def _request_save(self) -> None:
        self.save_requested.emit(self.get_values())

    def _request_discard(self) -> None:
        self.discard_requested.emit()

    def add_tab(self, title: str, groups: List[SettingGroup]) -> None:
        """Build a tab from a list of SettingGroup schemas and add it."""
        if self._tabs.count() == 0:
            self._insert_schema_tab(self._tabs.count(), title, groups)
            return

        index = self._tabs.addTab(self._make_lazy_placeholder(title), title)
        self._lazy_tab_builders[index] = lambda: self._insert_schema_tab(index, title, groups)

    def _insert_schema_tab(self, index: int, title: str, groups: List[SettingGroup]) -> None:
        scroll = self._build_schema_tab_widget(groups)
        if index < self._tabs.count():
            self._tabs.removeTab(index)
            self._tabs.insertTab(index, scroll, title)
        else:
            self._tabs.addTab(scroll, title)
        self.set_values(self._cached_values)

    def _build_schema_tab_widget(self, groups: List[SettingGroup]) -> QScrollArea:
        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)

        for schema in groups:
            card = QFrame()
            card.setObjectName("settingsCard")
            card.setStyleSheet(SETTINGS_CARD_FRAME_STYLE)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(0)

            header = QWidget()
            header.setObjectName("settingsCardHeader")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(16, 8, 12, 8)
            title = QLabel(self._translate_title(schema.title).upper())
            title.setObjectName("settingsCardTitle")
            self._section_headers.append((title, schema.title))
            header_layout.addWidget(title)
            header_layout.addStretch()

            widget = GenericSettingGroup(schema, compact=True)
            widget.setObjectName("settingsCardBody")
            widget.setTitle("")
            widget.setStyleSheet(SETTINGS_CARD_BODY_STYLE)
            widget.value_changed.connect(
                lambda k, v: self.value_changed_signal.emit(k, v, self._component_name)
            )
            self._groups.append(widget)
            if schema.axis_pairs and schema.fields:
                step_label = QLabel(self.tr("STEP") or "STEP")
                step_label.setStyleSheet(SETTINGS_FIELD_LABEL_STYLE)
                self._step_labels.append(step_label)
                header_layout.addWidget(step_label)
                step_group = QButtonGroup(header)
                step_group.setExclusive(True)
                for index, step in enumerate(schema.fields[0].step_options or []):
                    button = QPushButton(str(step))
                    button.setCheckable(True)
                    button.setStyleSheet(SETTINGS_STEP_STYLE)
                    button.setCursor(Qt.CursorShape.PointingHandCursor)
                    button.clicked.connect(lambda _checked, value=step, target=widget: target.set_step(value))
                    step_group.addButton(button)
                    button.setChecked(index == 1)
                    header_layout.addWidget(button)
                    if index == 1:
                        widget.set_step(step)
            card_layout.addWidget(header)
            card_body = QWidget()
            card_body.setObjectName("settingsCardContent")
            body_layout = QVBoxLayout(card_body)
            body_layout.setContentsMargins(16, 14, 16, 16)
            body_layout.addWidget(widget)
            card_layout.addWidget(card_body)
            content_layout.addWidget(card)

        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(TOUCH_SCROLL_AREA_STYLE)
        scroll.setWidget(content)
        return scroll

    def add_raw_tab(self, title: str, widget: QWidget) -> None:
        """Add a tab containing an arbitrary widget (not schema-driven)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(TOUCH_SCROLL_AREA_STYLE)
        scroll.setWidget(widget)
        self._tabs.addTab(scroll, title)

    def load(self, model) -> None:
        """Convert model → flat dict via mapper, then push into widgets."""
        if self._mapper is None:
            raise RuntimeError("No mapper configured on this SettingsView.")
        self.set_values(self._mapper(model))

    def set_values(self, flat: dict) -> None:
        self._cached_values = dict(flat)
        for group in self._groups:
            group.set_values(flat)

    def get_values(self) -> dict:
        result = dict(self._cached_values)
        for group in self._groups:
            result.update(group.get_values())
        return result

    def _on_tab_changed(self, index: int) -> None:
        builder = self._lazy_tab_builders.pop(index, None)
        if builder is not None:
            builder()
            self._tabs.setCurrentIndex(index)

    @staticmethod
    def _make_lazy_placeholder(title: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel(f"{title} will load when opened.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return widget
