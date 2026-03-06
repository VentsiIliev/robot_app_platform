from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QWidget

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.dashboard.widgets.ControlButtonsWidget import ControlButtonsWidget
from pl_gui.dashboard.widgets.RobotTrajectoryWidget import RobotTrajectoryWidget
from pl_gui.dashboard.config import DashboardConfig, ActionButtonConfig
from pl_gui.dashboard.layout.layout_manager import DashboardLayoutManager


class DashboardWidget(QWidget):
    """
    Pure UI facade for the dashboard.

    Accepts pre-built card widgets, places them in the configured grid,
    and routes typed setter calls to the correct card by card_id.

    Has zero knowledge of MessageBroker, topics, factories, or any
    external vision_service.
    """

    # User-action signals (adapter connects these to vision_service calls)
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    action_requested = pyqtSignal(str)  # emits action_id

    def __init__(
        self,
        config: DashboardConfig = None,
        action_buttons: list = None,
        cards: list = None,          # list of (widget, card_id, row, col)
        parent=None,
    ):
        super().__init__(parent)
        self.config = config or DashboardConfig()
        self._action_button_configs: list[ActionButtonConfig] = action_buttons or []
        self._action_buttons: dict[str, MaterialButton] = {}
        self._cards_input: list[tuple] = cards or []  # (widget, card_id, row, col)
        self._cards: dict[int, QWidget] = {}          # card_id → widget
        self.init_ui()

    # ------------------------------------------------------------------ #
    #  Typed setter API (called by DashboardAdapter)                      #
    # ------------------------------------------------------------------ #

    def set_cell_weight(self, card_id: int, grams: float) -> None:
        if card := self._cards.get(card_id):
            card.set_weight(grams)

    def set_cell_state(self, card_id: int, state: str) -> None:
        if card := self._cards.get(card_id):
            card.set_state(state)

    def set_cell_glue_type(self, card_id: int, glue_type: str) -> None:
        if card := self._cards.get(card_id):
            card.set_glue_type(glue_type)

    def set_trajectory_image(self, image) -> None:
        self.trajectory_widget.set_image(image)

    def update_trajectory_point(self, point) -> None:
        self.trajectory_widget.update_trajectory_point(point)

    def break_trajectory(self, _=None) -> None:
        self.trajectory_widget.break_trajectory()

    def enable_trajectory_drawing(self, _=None) -> None:
        self.trajectory_widget.enable_drawing()

    def disable_trajectory_drawing(self, _=None) -> None:
        self.trajectory_widget.disable_drawing()

    def set_start_enabled(self, enabled: bool) -> None:
        self.control_buttons.set_start_enabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self.control_buttons.set_stop_enabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self.control_buttons.set_pause_enabled(enabled)

    def set_pause_text(self, text: str) -> None:
        self.control_buttons.set_pause_text(text)

    def set_action_button_enabled(self, action_id: str, enabled: bool) -> None:
        if btn := self._action_buttons.get(action_id):
            btn.setEnabled(enabled)

    def set_action_button_text(self, action_id: str, text: str) -> None:
        if btn := self._action_buttons.get(action_id):
            btn.setText(text)

    # ------------------------------------------------------------------ #
    #  UI initialisation                                                   #
    # ------------------------------------------------------------------ #

    def init_ui(self):
        self.layout_manager = DashboardLayoutManager(self, self.config)

        self.trajectory_widget = RobotTrajectoryWidget(
            image_width=self.config.trajectory_width,
            image_height=self.config.trajectory_height,
            fps_ms=self.config.display_fps_ms,
            trail_length=self.config.trajectory_trail_length,
        )

        self.control_buttons = ControlButtonsWidget()
        self.control_buttons.start_clicked.connect(self.start_requested.emit)
        self.control_buttons.stop_clicked.connect(self.stop_requested.emit)
        self.control_buttons.pause_clicked.connect(self.pause_requested.emit)

        action_widgets = self._prepare_action_buttons()
        card_widgets = self._register_cards()

        self.layout_manager.setup_complete_layout(
            self.trajectory_widget,
            card_widgets,
            self.control_buttons,
            action_widgets,
        )

    def _prepare_action_buttons(self) -> list:
        """Build action buttons from config; return (widget, row, col, row_span, col_span) tuples."""
        result = []
        for cfg in self._action_button_configs:
            btn = MaterialButton(cfg.label, font_size=cfg.font_size)
            btn.setEnabled(cfg.enabled)
            action_id = cfg.action_id
            btn.clicked.connect(lambda _=False, aid=action_id: self.action_requested.emit(aid))
            self._action_buttons[action_id] = btn
            result.append((btn, cfg.row, cfg.col, cfg.row_span, cfg.col_span))
        return result

    def _register_cards(self) -> list:
        """Store card_id→widget mapping; return (widget, row, col) tuples for layout manager."""
        result = []
        for (widget, card_id, row, col) in self._cards_input:
            self._cards[card_id] = widget
            result.append((widget, row, col))
        return result

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #

    def clean_up(self):
        """Release resources. Broker subscriptions are managed by DashboardAdapter."""
        pass

    # ------------------------------------------------------------------ #
    #  Localization                                                        #
    # ------------------------------------------------------------------ #

    def retranslateUi(self) -> None:
        self.control_buttons.retranslateUi()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)