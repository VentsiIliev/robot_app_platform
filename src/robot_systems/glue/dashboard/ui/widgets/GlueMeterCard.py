from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame


from ..widgets.GlueMeterWidget import GlueMeterWidget
from pl_gui.utils.utils_widgets. MaterialButton import MaterialButton

# TODO fix the styles imports
from pl_gui.dashboard.resources.styles import *


class GlueMeterCard(QFrame):
    change_glue_requested = pyqtSignal(int)

    def __init__(self, label_text: str, index: int, capacity_grams: float = 5000.0):
        super().__init__()
        self.label_text = label_text
        self.index = index
        self.card_index = index
        self._current_state_str: str = "unknown"
        self._current_glue_type: Optional[str] = None
        self.meter_widget = GlueMeterWidget(index, capacity_grams=capacity_grams)
        self._build_ui()

    def set_weight(self, grams: float) -> None:
        self.meter_widget.set_weight(grams)

    def set_state(self, state_str: str) -> None:
        self._current_state_str = state_str
        self._update_indicator(state_str)
        self.meter_widget.set_state(state_str)

    def set_glue_type(self, glue_type: Optional[str]) -> None:
        self._current_glue_type = glue_type
        self.glue_type_label.setText(f"🧪 {glue_type}" if glue_type else self.tr("No glue configured"))

    def initialize_display(self, initial_state: Optional[dict], glue_type: Optional[str]) -> None:
        if initial_state:
            self.set_state(initial_state.get("current_state", "unknown"))
        if glue_type:
            self.set_glue_type(glue_type)

    def _update_indicator(self, state_str: str) -> None:
        state_config = {
            "unknown": {"color": STATUS_UNKNOWN, "text": self.tr("Unknown")},
            "initializing": {"color": STATUS_INITIALIZING, "text": self.tr("Initializing...")},
            "connecting": {"color": STATUS_INITIALIZING, "text": self.tr("Connecting...")},
            "connected": {"color": STATUS_READY, "text": self.tr("Connected")},
            "ready": {"color": STATUS_READY, "text": self.tr("Ready")},
            "low_weight": {"color": STATUS_LOW_WEIGHT, "text": self.tr("Low Weight")},
            "empty": {"color": STATUS_EMPTY, "text": self.tr("Empty")},
            "error": {"color": STATUS_ERROR, "text": self.tr("Error")},
            "disconnected": {"color": STATUS_DISCONNECTED, "text": self.tr("Disconnected")},
        }
        cfg = state_config.get(str(state_str).lower(), state_config["unknown"])
        self.state_indicator.setStyleSheet(
            f"QFrame {{ background-color: {cfg['color']}; border-radius: 8px; }}"
        )
        self.state_indicator.setToolTip(cfg["text"])

    def _build_ui(self) -> None:
        self.dragEnabled = True
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        self.title_label = QLabel(self.label_text)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(CARD_HEADER_STYLE)
        header_layout.addWidget(self.title_label, 1)
        self.state_indicator = QFrame()
        self.state_indicator.setFixedSize(16, 16)
        self.state_indicator.setToolTip("Unknown")
        self.state_indicator.setStyleSheet(
            f"QFrame {{ background-color: {STATUS_UNKNOWN}; border-radius: 8px; }}"
        )
        header_layout.addWidget(self.state_indicator, 0)
        main_layout.addLayout(header_layout)

        info_widget = QFrame()
        info_widget.setStyleSheet(INFO_FRAME_STYLE)
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setSpacing(10)
        self.glue_type_label = QLabel(self.tr("🧪 Loading..."))
        self.glue_type_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.glue_type_label.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: 600;
                color: #2c3e50;
                border: 1px solid #ccc;
                padding: 4px 8px;
                background-color: transparent;
            }
        """)
        info_layout.addWidget(self.glue_type_label, 1)
        self.change_glue_button = MaterialButton(self.tr("⚙ Change"))
        self.change_glue_button.clicked.connect(lambda: self.change_glue_requested.emit(self.index))
        info_layout.addWidget(self.change_glue_button)
        main_layout.addWidget(info_widget)

        main_layout.addWidget(self.meter_widget)
        self.meter_widget.setStyleSheet(METER_FRAME_STYLE)
        main_layout.addStretch()
        self.setStyleSheet(CARD_STYLE)

    # ------------------------------------------------------------------ #
    #  Localization                                                        #
    # ------------------------------------------------------------------ #

    def retranslateUi(self) -> None:
        self.change_glue_button.setText(self.tr("⚙ Change"))
        self._update_indicator(self._current_state_str)
        if self._current_glue_type is None:
            self.glue_type_label.setText(self.tr("🧪 Loading..."))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

