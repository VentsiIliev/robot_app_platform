from __future__ import annotations

from html import escape

import cv2
from PyQt6.QtCore import QEvent, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    APP_PAGE_TITLE_STYLE,
    BG_COLOR,
    BORDER,
    ERROR_COLOR,
    GHOST_BTN_STYLE,
    PRIMARY,
    SECONDARY_BG,
    STATUS_OK,
    TERTIARY_TEXT,
    TEXT_COLOR,
    TOUCH_SCROLL_AREA_STYLE,
    TOUCH_COMBO_STYLE,
)
from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.applications.base.i_application_view import IApplicationView
from src.shared_contracts.declarations import WorkAreaDefinition


_CARD_STYLE = (
    f"QFrame#workAreaCard {{ background: white; border: 1px solid {BORDER};"
    " border-radius: 18px; }"
)
_SMALL_BUTTON_STYLE = f"""
QPushButton {{
    background: {SECONDARY_BG}; color: {PRIMARY}; border: none;
    border-radius: 12px; min-height: 48px; font-size: 13pt; font-weight: bold;
}}
QPushButton:checked, QPushButton:pressed {{ background: {PRIMARY}; color: white; }}
QPushButton:disabled {{ color: {TERTIARY_TEXT}; }}
"""
_ROLE_STYLE = f"""
QPushButton {{
    background: {SECONDARY_BG}; color: {TERTIARY_TEXT}; border: none;
    border-radius: 11px; min-height: 48px; font-size: 11pt; font-weight: bold;
}}
QPushButton:checked {{ background: {PRIMARY}; color: white; }}
QPushButton:disabled {{ color: {TERTIARY_TEXT}; }}
"""
class WorkAreaSettingsView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    work_area_changed = pyqtSignal(str)
    save_area_requested = pyqtSignal(str)
    vision_state_changed = pyqtSignal(str)

    def __init__(
        self,
        work_area_definitions: list[WorkAreaDefinition] | None = None,
        parent=None,
    ):
        self._work_area_definitions = list(work_area_definitions or [])
        self._active_area_key = ""
        self._saved_corners: dict[str, list[tuple[float, float]]] = {}
        self._selected_corner = 0
        self._frame_size: tuple[int, int] | None = None
        self._vision_state = "unknown"
        super().__init__("WorkAreaSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 16, 40, 20)
        root.setSpacing(16)

        self._page_title = QLabel()
        self._page_title.setStyleSheet(APP_PAGE_TITLE_STYLE)
        root.addWidget(self._page_title)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        root.addLayout(columns, 1)
        columns.addWidget(self._build_preview_panel(), 5)
        columns.addWidget(self._build_editor_panel(), 2)
        self._connect_signals()
        self.vision_state_changed.connect(self._on_vision_state_changed)
        self._rebuild_area_choices()
        self.retranslateUi()

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("workAreaCard")
        card.setStyleSheet(_CARD_STYLE)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        return card, layout

    def _build_preview_panel(self) -> QWidget:
        card, layout = self._card()
        header = QHBoxLayout()
        header.setContentsMargins(16, 12, 16, 12)
        self._state_label = QLabel()
        self._state_label.setStyleSheet(
            f"color: {PRIMARY}; background: {SECONDARY_BG};"
            " border-radius: 12px; padding: 7px 12px;"
        )
        header.addWidget(self._state_label)
        header.addStretch(1)
        self._detection_legend = QLabel()
        self._brightness_legend = QLabel()
        for label in (self._detection_legend, self._brightness_legend):
            label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
            header.addWidget(label)
        layout.addLayout(header)

        self._preview_label = CameraView()
        self._preview_label.set_toolbar_visible(False)
        self._preview_label.setMinimumSize(400, 340)
        layout.addWidget(self._preview_label, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(16, 12, 16, 12)
        footer.setSpacing(8)
        self._preview_hint = QLabel()
        self._preview_hint.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        footer.addWidget(self._preview_hint, 1)
        self._zoom_out = self._small_button("−")
        self._zoom_in = self._small_button("+")
        self._zoom_reset = self._small_button("⊙")
        self._zoom_value = QLabel("100%")
        self._zoom_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_value.setMinimumWidth(52)
        self._zoom_value.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent;")
        for widget in (self._zoom_out, self._zoom_value, self._zoom_in, self._zoom_reset):
            footer.addWidget(widget)
        layout.addLayout(footer)
        return card

    def _build_editor_panel(self) -> QWidget:
        card, layout = self._card()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(TOUCH_SCROLL_AREA_STYLE)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        scroll.setWidget(content)
        layout.addWidget(scroll)
        body = QVBoxLayout(content)
        body.setContentsMargins(22, 20, 22, 20)
        body.setSpacing(14)

        self._editor_title = QLabel()
        self._editor_title.setStyleSheet(
            f"color: {TEXT_COLOR}; background: transparent; font-size: 17pt; font-weight: bold;"
        )
        body.addWidget(self._editor_title)
        self._active_area_label = QLabel()
        self._active_area_label.setStyleSheet(
            f"color: {PRIMARY}; background: {SECONDARY_BG}; border-radius: 12px;"
            " padding: 7px 12px;"
        )
        body.addWidget(self._active_area_label, 0, Qt.AlignmentFlag.AlignLeft)

        self._work_area_label = QLabel()
        self._work_area_label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        body.addWidget(self._work_area_label)
        self._work_area_field = QFrame()
        self._work_area_field.setObjectName("touchCombo")
        self._work_area_field.setStyleSheet(TOUCH_COMBO_STYLE)
        field_layout = QHBoxLayout(self._work_area_field)
        field_layout.setContentsMargins(2, 2, 4, 2)
        field_layout.setSpacing(0)
        self._work_area_combo = QComboBox()
        self._work_area_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        field_layout.addWidget(self._work_area_combo, 1)
        self._work_area_dropdown = QPushButton("▾")
        self._work_area_dropdown.setObjectName("comboDrop")
        self._work_area_dropdown.setFixedSize(40, 48)
        self._work_area_dropdown.setCursor(Qt.CursorShape.PointingHandCursor)
        field_layout.addWidget(self._work_area_dropdown)
        body.addWidget(self._work_area_field)

        self._roi_label = QLabel()
        self._roi_label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        body.addWidget(self._roi_label)
        roles = QHBoxLayout()
        roles.setSpacing(0)
        self._detection_btn = self._role_button()
        self._brightness_btn = self._role_button()
        roles.addWidget(self._detection_btn, 1)
        roles.addWidget(self._brightness_btn, 1)
        body.addLayout(roles)

        self._corner_label = QLabel()
        self._corner_label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        body.addWidget(self._corner_label)
        corners = QHBoxLayout()
        corners.setSpacing(8)
        self._corner_group = QButtonGroup(self)
        self._corner_buttons: list[QPushButton] = []
        for index in range(4):
            button = self._small_button(str(index + 1), checkable=True)
            self._corner_group.addButton(button, index)
            self._corner_buttons.append(button)
            corners.addWidget(button, 1)
        self._corner_buttons[0].setChecked(True)
        body.addLayout(corners)

        nudge_row = QHBoxLayout()
        nudge_row.setSpacing(12)
        pad = QGridLayout()
        pad.setHorizontalSpacing(8)
        pad.setVerticalSpacing(8)
        self._up_button = self._small_button("▲")
        self._left_button = self._small_button("◀")
        self._right_button = self._small_button("▶")
        self._down_button = self._small_button("▼")
        for button in (
            self._up_button, self._left_button, self._right_button, self._down_button
        ):
            button.setFixedSize(52, 52)
        self._coordinate_label = QLabel("—")
        self._coordinate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._coordinate_label.setFixedSize(52, 52)
        self._coordinate_label.setStyleSheet(
            f"color: {TERTIARY_TEXT}; background: transparent; font-size: 10pt;"
        )
        self._step_label = QLabel()
        self._step_label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_group = QButtonGroup(self)
        self._step_buttons: list[QPushButton] = []
        step_column = QVBoxLayout()
        step_column.setSpacing(4)
        step_column.addWidget(self._step_label)
        for step in (1, 5, 10):
            button = self._small_button(str(step), checkable=True)
            button.setFixedSize(68, 38)
            self._step_group.addButton(button, step)
            self._step_buttons.append(button)
            step_column.addWidget(button)
        self._step_buttons[1].setChecked(True)
        pad.addWidget(self._up_button, 0, 1)
        pad.addWidget(self._left_button, 1, 0)
        pad.addWidget(self._coordinate_label, 1, 1)
        pad.addWidget(self._right_button, 1, 2)
        pad.addWidget(self._down_button, 2, 1)
        nudge_row.addLayout(pad)
        nudge_row.addLayout(step_column)
        nudge_row.addStretch(1)
        body.addLayout(nudge_row)
        body.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self._save_btn = QPushButton()
        self._save_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn = QPushButton()
        self._reset_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        actions.addWidget(self._save_btn, 2)
        actions.addWidget(self._reset_btn, 1)
        body.addLayout(actions)
        return card

    @staticmethod
    def _small_button(text: str, *, checkable: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(checkable)
        button.setStyleSheet(_SMALL_BUTTON_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumWidth(44)
        return button

    @staticmethod
    def _role_button() -> QPushButton:
        button = QPushButton()
        button.setCheckable(True)
        button.setStyleSheet(_ROLE_STYLE)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _connect_signals(self) -> None:
        self._work_area_combo.currentIndexChanged.connect(self._on_work_area_changed)
        self._work_area_dropdown.clicked.connect(self._work_area_combo.showPopup)
        self._detection_btn.clicked.connect(self._on_detection_clicked)
        self._brightness_btn.clicked.connect(self._on_brightness_clicked)
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        self._corner_group.idClicked.connect(self._on_corner_selected)
        self._preview_label.corner_updated.connect(self._on_corner_updated)
        self._preview_label.zoom_changed.connect(self._on_zoom_changed)
        self._zoom_out.clicked.connect(self._preview_label.zoom_out)
        self._zoom_in.clicked.connect(self._preview_label.zoom_in)
        self._zoom_reset.clicked.connect(self._preview_label.reset_zoom)
        self._up_button.clicked.connect(self._nudge_up)
        self._down_button.clicked.connect(self._nudge_down)
        self._left_button.clicked.connect(self._nudge_left)
        self._right_button.clicked.connect(self._nudge_right)

    def _rebuild_area_choices(self) -> None:
        self._work_area_combo.blockSignals(True)
        self._work_area_combo.clear()
        for definition in self._work_area_definitions:
            self._work_area_combo.addItem(definition.label, definition.id)
            if definition.supports_detection_roi:
                self.preview_label.add_area(definition.detection_area_key(), definition.color)
            if definition.supports_brightness_roi:
                self.preview_label.add_area(definition.brightness_area_key(), PRIMARY)
        self._work_area_combo.blockSignals(False)
        self._select_default_role()

    def _select_default_role(self) -> None:
        definition = self.current_work_area_definition()
        self._detection_btn.setChecked(False)
        self._brightness_btn.setChecked(False)
        self._detection_btn.setEnabled(bool(definition and definition.supports_detection_roi))
        self._brightness_btn.setEnabled(bool(definition and definition.supports_brightness_roi))
        self._detection_legend.setStyleSheet(
            f"color: {definition.color if definition else TERTIARY_TEXT}; background: transparent;"
        )
        self._brightness_legend.setStyleSheet(
            f"color: {PRIMARY}; background: transparent;"
        )
        if definition is None:
            self.set_active_area_key("")
        elif definition.supports_detection_roi:
            self._detection_btn.setChecked(True)
            self.set_active_area_key(definition.detection_area_key())
        elif definition.supports_brightness_roi:
            self._brightness_btn.setChecked(True)
            self.set_active_area_key(definition.brightness_area_key())
        else:
            self.set_active_area_key("")

    def _on_work_area_changed(self) -> None:
        self._select_default_role()
        self.work_area_changed.emit(self.current_work_area_id())

    def _on_detection_clicked(self) -> None:
        definition = self.current_work_area_definition()
        if definition is not None and definition.supports_detection_roi:
            self._detection_btn.setChecked(True)
            self._brightness_btn.setChecked(False)
            self.set_active_area_key(definition.detection_area_key())

    def _on_brightness_clicked(self) -> None:
        definition = self.current_work_area_definition()
        if definition is not None and definition.supports_brightness_roi:
            self._brightness_btn.setChecked(True)
            self._detection_btn.setChecked(False)
            self.set_active_area_key(definition.brightness_area_key())

    def _on_save_clicked(self) -> None:
        if self._active_area_key and len(self.get_area_corners(self._active_area_key)) == 4:
            self.save_area_requested.emit(self._active_area_key)

    def _on_reset_clicked(self) -> None:
        if self._active_area_key:
            self.preview_label.set_area_corners(
                self._active_area_key, self._saved_corners.get(self._active_area_key, [])
            )
            self._refresh_corner_state()

    def _on_corner_selected(self, index: int) -> None:
        self._selected_corner = index
        self._refresh_corner_state()

    def _on_corner_updated(self, area_key: str, index: int, _x: float, _y: float) -> None:
        if area_key == self._active_area_key:
            self._selected_corner = index
            self._corner_buttons[index].setChecked(True)
            self._refresh_corner_state()

    def _on_zoom_changed(self, percent: int) -> None:
        self._zoom_value.setText(f"{percent}%")

    def _nudge_up(self) -> None:
        self._nudge(0, -1)

    def _nudge_down(self) -> None:
        self._nudge(0, 1)

    def _nudge_left(self) -> None:
        self._nudge(-1, 0)

    def _nudge_right(self) -> None:
        self._nudge(1, 0)

    def _nudge(self, dx: int, dy: int) -> None:
        if not self._active_area_key or self._frame_size is None:
            return
        points = self.preview_label.get_area_corners(self._active_area_key)
        if self._selected_corner >= len(points):
            return
        width, height = self._frame_size
        step = self._step_group.checkedId()
        x, y = points[self._selected_corner]
        points[self._selected_corner] = (
            max(0.0, min(1.0, x + dx * step / width)),
            max(0.0, min(1.0, y + dy * step / height)),
        )
        self.preview_label.set_area_corners(self._active_area_key, points)
        self._refresh_corner_state()

    def _refresh_corner_state(self) -> None:
        points = self.get_area_corners(self._active_area_key) if self._active_area_key else []
        has_corner = self._selected_corner < len(points)
        can_nudge = has_corner and self._frame_size is not None
        for button in (self._up_button, self._down_button, self._left_button, self._right_button):
            button.setEnabled(can_nudge)
        self._save_btn.setEnabled(len(points) == 4)
        self._reset_btn.setEnabled(
            bool(self._active_area_key)
            and points != self._saved_corners.get(self._active_area_key, [])
        )
        if has_corner and self._frame_size is not None:
            x, y = points[self._selected_corner]
            width, height = self._frame_size
            self._coordinate_label.setText(
                f"x {round(x * width)}\ny {round(y * height)}"
            )
        else:
            self._coordinate_label.setText("—")

    @pyqtSlot(str)
    def _on_vision_state_changed(self, state: str) -> None:
        self._vision_state = str(state or "unknown").lower()
        self.retranslateUi()

    def set_work_area_options(self, definitions: list[WorkAreaDefinition]) -> None:
        self._work_area_definitions = list(definitions)
        self._rebuild_area_choices()

    def set_current_work_area_id(self, area_id: str) -> None:
        index = self._work_area_combo.findData(str(area_id or ""))
        if index >= 0:
            self._work_area_combo.setCurrentIndex(index)

    def current_work_area_id(self) -> str:
        return str(self._work_area_combo.currentData() or "")

    def current_work_area_definition(self) -> WorkAreaDefinition | None:
        area_id = self.current_work_area_id()
        for definition in self._work_area_definitions:
            if definition.id == area_id:
                return definition
        return None

    @property
    def work_area_definitions(self) -> list[WorkAreaDefinition]:
        return list(self._work_area_definitions)

    def set_active_area_key(self, area_key: str) -> None:
        self._active_area_key = str(area_key or "")
        self.preview_label.set_active_area(self._active_area_key or None)
        self._selected_corner = 0
        self._corner_buttons[0].setChecked(True)
        self._update_active_area_label()
        self._refresh_corner_state()

    def _update_active_area_label(self) -> None:
        definition = self.current_work_area_definition()
        if not self._active_area_key or definition is None:
            self._active_area_label.setText(self.tr("No ROI selected"))
            return
        role = self.tr("Brightness ROI") if self._active_area_key == definition.brightness_area_key() else self.tr("Detection ROI")
        self._active_area_label.setText(f"{definition.label} · {role}")

    def set_vision_state(self, state: str) -> None:
        self.vision_state_changed.emit(state)

    def update_camera_view(self, image) -> None:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        self._frame_size = (width, height)
        qimg = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888)
        self.preview_label.set_frame(QPixmap.fromImage(qimg))
        self._refresh_corner_state()

    def set_area_corners(self, area_name: str, normalized_points: list) -> None:
        points = [tuple(point) for point in normalized_points]
        self.preview_label.set_area_corners(area_name, points)
        self._saved_corners[area_name] = list(points)
        self._refresh_corner_state()

    def mark_area_saved(self, area_name: str) -> None:
        self._saved_corners[area_name] = self.get_area_corners(area_name)
        self._refresh_corner_state()

    def get_area_corners(self, area_name: str) -> list:
        return self.preview_label.get_area_corners(area_name)

    @property
    def preview_label(self) -> CameraView:
        return self._preview_label

    def retranslateUi(self) -> None:
        self._page_title.setText(self.tr("Work area editor"))
        self._editor_title.setText(self.tr("Work area"))
        self._work_area_label.setText(self.tr("Work area"))
        self._work_area_dropdown.setAccessibleName(self.tr("Choose work area"))
        self._roi_label.setText(self.tr("ROI"))
        self._corner_label.setText(self.tr("Corner"))
        self._step_label.setText(self.tr("Step (px)"))
        self._detection_btn.setText(self.tr("Detection ROI"))
        self._brightness_btn.setText(self.tr("Brightness ROI"))
        self._detection_legend.setText("● " + self.tr("Detection ROI"))
        self._brightness_legend.setText("● " + self.tr("Brightness ROI"))
        self._preview_hint.setText(
            self.tr("Drag a corner on the preview, or use the arrows on the right.")
        )
        self._save_btn.setText(self.tr("Save ROI"))
        self._reset_btn.setText(self.tr("Reset"))
        self._zoom_out.setAccessibleName(self.tr("Zoom out"))
        self._zoom_in.setAccessibleName(self.tr("Zoom in"))
        self._zoom_reset.setAccessibleName(self.tr("Reset zoom"))
        self._up_button.setAccessibleName(self.tr("Move corner up"))
        self._down_button.setAccessibleName(self.tr("Move corner down"))
        self._left_button.setAccessibleName(self.tr("Move corner left"))
        self._right_button.setAccessibleName(self.tr("Move corner right"))
        self._state_label.setText(
            f'<span style="color: {ERROR_COLOR if self._vision_state == "error" else STATUS_OK};">●</span> '
            f'{escape(self.tr("Vision service"))}: {escape(self._vision_state)}'
        )
        self._state_label.setStyleSheet(
            f"color: {PRIMARY}; background: {SECONDARY_BG};"
            " border-radius: 12px; padding: 7px 12px;"
        )
        self._update_active_area_label()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)
