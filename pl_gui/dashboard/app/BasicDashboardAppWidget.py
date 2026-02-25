from PyQt6.QtCore import pyqtSignal, QEvent


from pl_gui.shell.base_app_widget.AppWidget import AppWidget
try:
    from pl_gui.dashboard.DashboardWidget import DashboardWidget
except ImportError:
    from pl_gui.dashboard.DashboardWidget import DashboardWidget


class BasicDashboardAppWidget(AppWidget):
    """
    Level 3 — generic UI shell for any dashboard adapter.

    Responsibilities:
      - Builds and owns DashboardWidget internally
      - Re-emits DashboardWidget signals as its own public API
      - Exposes setter methods that the adapter calls to update the UI
      - Forwards Qt LanguageChange to retranslateUi()

    Has zero knowledge of any adapter, container, or backend.
    The adapter receives this widget and wires itself to it.
    """

    LOGOUT_REQUEST   = pyqtSignal()
    start_requested  = pyqtSignal()
    pause_requested  = pyqtSignal()
    stop_requested   = pyqtSignal()
    action_requested = pyqtSignal(str)
    language_changed = pyqtSignal()

    def __init__(self,  parent=None):

        super().__init__("Dashboard", parent)  # AppWidget calls setup_ui() automatically

    # ------------------------------------------------------------------ #
    #  UI setup                                                            #
    # ------------------------------------------------------------------ #

    def setup_ui(self):
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._dashboard = DashboardWidget()
        layout.addWidget(self._dashboard)

        # Re-emit dashboard signals as this widget's own public signals
        self._dashboard.start_requested.connect(self.start_requested.emit)
        self._dashboard.stop_requested.connect(self.stop_requested.emit)
        self._dashboard.pause_requested.connect(self.pause_requested.emit)
        self._dashboard.action_requested.connect(self.action_requested.emit)

    # ------------------------------------------------------------------ #
    #  Setter API — called exclusively by the adapter                     #
    # ------------------------------------------------------------------ #

    def set_cell_weight(self, card_id: int, grams: float) -> None:
        self._dashboard.set_cell_weight(card_id, grams)

    def set_cell_state(self, card_id: int, state: str) -> None:
        self._dashboard.set_cell_state(card_id, state)

    def set_cell_glue_type(self, card_id: int, glue_type: str) -> None:
        self._dashboard.set_cell_glue_type(card_id, glue_type)

    def set_trajectory_image(self, image) -> None:
        self._dashboard.set_trajectory_image(image)

    def update_trajectory_point(self, point) -> None:
        self._dashboard.update_trajectory_point(point)

    def break_trajectory(self, _=None) -> None:
        self._dashboard.break_trajectory()

    def enable_trajectory_drawing(self, _=None) -> None:
        self._dashboard.enable_trajectory_drawing()

    def disable_trajectory_drawing(self, _=None) -> None:
        self._dashboard.disable_trajectory_drawing()

    def set_start_enabled(self, enabled: bool) -> None:
        self._dashboard.set_start_enabled(enabled)

    def set_stop_enabled(self, enabled: bool) -> None:
        self._dashboard.set_stop_enabled(enabled)

    def set_pause_enabled(self, enabled: bool) -> None:
        self._dashboard.set_pause_enabled(enabled)

    def set_pause_text(self, text: str) -> None:
        self._dashboard.set_pause_text(text)

    def set_action_button_text(self, action_id: str, text: str) -> None:
        self._dashboard.set_action_button_text(action_id, text)

    def set_action_button_enabled(self, action_id: str, enabled: bool) -> None:
        self._dashboard.set_action_button_enabled(action_id, enabled)

    def get_card(self, card_id: int):
        """Return the card widget for *card_id* (used by adapter for sub-signals)."""
        return self._dashboard._cards.get(card_id)

    # ------------------------------------------------------------------ #
    #  Localization                                                        #
    # ------------------------------------------------------------------ #

    def retranslateUi(self) -> None:
        self._dashboard.retranslateUi()
        self.language_changed.emit()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    # ------------------------------------------------------------------ #
    #  Qt lifecycle                                                        #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        super().closeEvent(event)
        self.LOGOUT_REQUEST.emit()

    def clean_up(self):
        if hasattr(super(), "clean_up"):
            super().clean_up()
