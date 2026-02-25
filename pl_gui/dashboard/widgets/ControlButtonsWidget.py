from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy
from PyQt6.QtCore import pyqtSignal, QEvent

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
class ControlButtonsWidget(QWidget):
    """
    Pure UI widget: Start / Stop / Pause buttons.

    Zero knowledge of ApplicationState, MessageBroker, or topics.
    The adapter drives all state changes via the public setter API.
    """

    start_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.init_ui()
        self.connect_signals()

    # ------------------------------------------------------------------ #
    #  UI Setup                                                            #
    # ------------------------------------------------------------------ #

    def _create_frame_with_layout(self, min_height=120) -> tuple[QFrame, QHBoxLayout]:
        frame = QFrame()
        frame.setStyleSheet("QFrame {border: none; background-color: transparent;}")
        frame.setMinimumHeight(min_height)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        return frame, layout

    def _create_button(self, text: str = "", font_size=20, enabled=False) -> MaterialButton:
        btn = MaterialButton(text, font_size=font_size)
        btn.setEnabled(enabled)
        return btn

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_frame, top_layout = self._create_frame_with_layout()
        bottom_frame, bottom_layout = self._create_frame_with_layout()

        self.start_btn = self._create_button(text=self.tr("Start"))
        self.stop_btn  = self._create_button(text=self.tr("Stop"))
        self.pause_btn = self._create_button(text=self.tr("Pause"))

        top_layout.addWidget(self.start_btn)
        top_layout.addWidget(self.pause_btn)
        bottom_layout.addWidget(self.stop_btn)

        main_layout.addWidget(top_frame)
        main_layout.addWidget(bottom_frame)

    # ------------------------------------------------------------------ #
    #  Signals                                                             #
    # ------------------------------------------------------------------ #

    def connect_signals(self) -> None:
        self.start_btn.clicked.connect(self.start_clicked.emit)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.pause_btn.clicked.connect(self.pause_clicked.emit)

    # ------------------------------------------------------------------ #
    #  Public setter API — called by the adapter                          #
    # ------------------------------------------------------------------ #

    def set_start_enabled(self, enabled: bool) -> None:
        self.start_btn.setEnabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self.stop_btn.setEnabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self.pause_btn.setEnabled(enabled)

    def set_pause_text(self, text: str) -> None:
        self.pause_btn.setText(text)

    # ------------------------------------------------------------------ #
    #  Localization                                                        #
    # ------------------------------------------------------------------ #

    def retranslateUi(self) -> None:
        self.start_btn.setText(self.tr("Start"))
        self.stop_btn.setText(self.tr("Stop"))
        self.pause_btn.setText(self.tr("Pause"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)


