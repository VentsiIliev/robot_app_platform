from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BORDER,
    LABEL_STYLE,
    SECONDARY_BG,
    TERTIARY_TEXT,
    TOUCH_COMBO_STYLE,
)
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField


class PaintHeadSettingsView(QWidget):
    save_requested = pyqtSignal(int, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._build_ui()
        self.retranslateUi()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        self._box = QGroupBox()
        self._box.setStyleSheet(f"""
            QGroupBox {{ background: white; border: 1px solid {BORDER};
                border-radius: 18px; margin-top: 0; padding-top: 0; }}
        """)
        form = QVBoxLayout(self._box)
        form.setContentsMargins(22, 20, 22, 20)
        form.setSpacing(12)

        self._section_title = QLabel()
        self._section_title.setStyleSheet(LABEL_STYLE)
        form.addWidget(self._section_title)
        self._direction_label = QLabel()
        self._direction_label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        direction_frame = QFrame()
        direction_frame.setObjectName("touchCombo")
        direction_frame.setStyleSheet(TOUCH_COMBO_STYLE)
        direction_row = QHBoxLayout(direction_frame)
        direction_row.setContentsMargins(2, 2, 4, 2)
        direction_row.setSpacing(0)
        self._direction = QComboBox()
        self._direction.setCursor(Qt.CursorShape.PointingHandCursor)
        direction_row.addWidget(self._direction, 1)
        direction_button = QPushButton("▾")
        direction_button.setObjectName("comboDrop")
        direction_button.setFixedSize(40, 48)
        direction_button.setCursor(Qt.CursorShape.PointingHandCursor)
        direction_button.clicked.connect(self._direction.showPopup)
        direction_row.addWidget(direction_button)
        form.addWidget(self._direction_label)
        form.addWidget(direction_frame)

        numbers = QHBoxLayout()
        spacing_column = QVBoxLayout()
        self._spacing_label = QLabel()
        self._spacing_label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        self._spacing = KeyboardNumberField()
        self._spacing.setRange(1, 65535)
        self._spacing.valueChanged.connect(self._on_number_changed)
        spacing_column.addWidget(self._spacing_label)
        spacing_column.addWidget(self._spacing)
        numbers.addLayout(spacing_column)

        count_column = QVBoxLayout()
        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        self._count = KeyboardNumberField()
        self._count.setRange(1, 24)
        self._count.valueChanged.connect(self._on_number_changed)
        count_column.addWidget(self._count_label)
        count_column.addWidget(self._count)
        numbers.addLayout(count_column)
        form.addLayout(numbers)

        self._range = QLabel()
        self._range.setStyleSheet(
            f"color: {TERTIARY_TEXT}; background: {SECONDARY_BG};"
            " border-radius: 12px; padding: 10px 14px;"
        )
        form.addWidget(self._range)
        self._save_button = QPushButton()
        self._save_button.setStyleSheet(ACTION_BTN_STYLE)
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_button.clicked.connect(self._on_save)
        form.addWidget(self._save_button, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._box)

        self._status = QLabel()
        self._status.setWordWrap(True)
        root.addWidget(self._status)

    def set_settings(self, sign: int, spacing: int, count: int, minimum: int) -> None:
        self._direction.setCurrentIndex(0 if sign == -1 else 1)
        self._spacing.setValue(spacing)
        self._count.setValue(count)
        self._minimum = minimum
        self._update_range()
        self._status.setText("")

    def set_busy(self, busy: bool) -> None:
        for widget in (self._direction, self._spacing, self._count, self._save_button):
            widget.setEnabled(not busy)

    def set_saved(self, sign: int, spacing: int, count: int, minimum: int) -> None:
        self.set_settings(sign, spacing, count, minimum)
        self._status.setText(self.tr("Paint-head settings saved and applied immediately."))

    def set_error(self, message: str) -> None:
        self._status.setText(message)

    def _on_save(self) -> None:
        self.save_requested.emit(
            int(self._direction.currentData()),
            self._spacing.value(),
            self._count.value(),
        )

    def _on_number_changed(self, _value: int) -> None:
        self._update_range()

    def _update_range(self) -> None:
        minimum = getattr(self, "_minimum", 45)
        maximum = minimum + self._spacing.value() * (self._count.value() - 1)
        self._range.setText(
            self.tr("Preset register range: {minimum}–{maximum}").format(
                minimum=minimum, maximum=maximum
            )
        )

    def retranslateUi(self) -> None:
        current_sign = self._direction.currentData()
        self._direction.clear()
        self._direction.addItem(self.tr("More paint decreases register value"), -1)
        self._direction.addItem(self.tr("More paint increases register value"), 1)
        self._direction.setCurrentIndex(0 if current_sign in (None, -1) else 1)
        self._box.setTitle("")
        self._section_title.setText(self.tr("Paint Head Configuration"))
        self._direction_label.setText(self.tr("Relative move direction"))
        self._spacing_label.setText(self.tr("Register units between settings"))
        self._count_label.setText(self.tr("Number of settings"))
        self._save_button.setText(self.tr("Save Paint Head Settings"))
        self._update_range()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)
