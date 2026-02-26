from abc import abstractmethod

from pl_gui.shell.base_app_widget.AppWidget import AppWidget


class IPluginView(AppWidget):
    """
    Base class for all plugin views.

    Extends AppWidget — required by the shell (provides app_closed signal).
    Enforces the two rules of the view layer:
      - setup_ui()  : build widgets, wire internal signals to outbound pyqtSignals
      - clean_up()  : stop timers, threads, subscriptions on widget destruction
    """

    @abstractmethod
    def setup_ui(self) -> None: ...

    @abstractmethod
    def clean_up(self) -> None: ...