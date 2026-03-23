from abc import abstractmethod
from typing import Optional

from PyQt6.QtCore import pyqtSignal

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.applications.base.drawer_toggle import DrawerToggle
from src.applications.base.robot_jog_widget import RobotJogWidget


class IApplicationView(AppWidget):
    """
    Base class for all application views.

    Extends AppWidget — required by the shell (provides app_closed signal).
    Enforces the two rules of the view layer:
      - setup_ui()  : build widgets, wire internal signals to outbound pyqtSignals
      - clean_up()  : stop timers, threads, subscriptions on widget destruction
    """

    SHOW_JOG_WIDGET = False
    JOG_FRAME_SELECTOR_ENABLED = False
    JOG_DRAWER_SIDE = "right"
    JOG_DRAWER_WIDTH = 320

    jog_requested = pyqtSignal(str, str, str, float)
    jog_started = pyqtSignal(str)
    jog_stopped = pyqtSignal(str)

    def __init__(self, title: str, parent=None):
        self._drawer: Optional[DrawerToggle] = None
        self._jog_widget: Optional[RobotJogWidget] = None
        super().__init__(title, parent)
        self._install_jog_widget()

    def _install_jog_widget(self) -> None:
        self._drawer = DrawerToggle(
            self,
            side=self.JOG_DRAWER_SIDE,
            width=self.JOG_DRAWER_WIDTH,
        )
        self._jog_widget = RobotJogWidget()
        self._jog_widget.enable_frame_selector(self.JOG_FRAME_SELECTOR_ENABLED)
        self._drawer.add_widget(self._jog_widget)
        self._jog_widget.jog_requested.connect(self.jog_requested)
        self._jog_widget.jog_started.connect(self.jog_started)
        self._jog_widget.jog_stopped.connect(self.jog_stopped)

        frame_changed = getattr(self, "_on_jog_frame_changed", None)
        if callable(frame_changed):
            self._jog_widget.frame_changed.connect(frame_changed)

        configure = getattr(self, "_configure_jog_widget", None)
        if callable(configure):
            configure()

        self.enable_jog_widget(self.SHOW_JOG_WIDGET)

    def enable_jog_widget(self, enabled: bool) -> None:
        if self._drawer is not None:
            self._drawer.set_visible(enabled)

    def set_jog_position(self, pos: list) -> None:
        if self._jog_widget is not None:
            self._jog_widget.set_position(pos)

    def set_jog_frame_options(self, names: list[str], default: str | None = None) -> None:
        if self._jog_widget is not None:
            self._jog_widget.set_frame_options(names, default=default)

    def set_jog_frame(self, name: str) -> None:
        if self._jog_widget is not None:
            self._jog_widget.set_frame(name)

    def get_jog_frame(self) -> str:
        if self._jog_widget is None:
            return ""
        return self._jog_widget.get_frame()

    @abstractmethod
    def setup_ui(self) -> None: ...

    @abstractmethod
    def clean_up(self) -> None: ...
