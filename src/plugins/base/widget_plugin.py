import logging
from typing import Callable, Optional
from PyQt6.QtWidgets import QWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.plugins.base.plugin_interface import IPlugin


class WidgetPlugin(IPlugin):
    """
    Generic IPlugin adapter that wraps any widget_factory callable.
    The widget_factory receives IMessagingService so it can subscribe
    to live topics if needed.
    """

    def __init__(self, widget_factory: Callable[[IMessagingService], QWidget]):
        self._logger         = logging.getLogger(self.__class__.__name__)
        self._widget_factory = widget_factory
        self._messaging_service: Optional[IMessagingService] = None

    def register(self, messaging_service: IMessagingService) -> None:
        self._messaging_service = messaging_service
        self._logger.debug("WidgetPlugin registered")

    def create_widget(self) -> QWidget:
        return self._widget_factory(self._messaging_service)
