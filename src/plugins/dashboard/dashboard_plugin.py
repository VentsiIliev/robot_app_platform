import logging
from typing import Callable, Optional

from PyQt6.QtWidgets import QWidget

from src.engine.core.message_broker import MessageBroker
from src.plugins.base.plugin_interface import IPlugin


class DashboardPlugin(IPlugin):
    """
    Generic dashboard plugin shell.
    Has zero knowledge of which app's dashboard it hosts.
    The widget_factory callable is provided at construction time by bootstrap.
    """

    def __init__(self, widget_factory: Callable[[MessageBroker], QWidget]):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._widget_factory = widget_factory
        self._broker: Optional[MessageBroker] = None

    def register(self, broker: MessageBroker) -> None:
        self._broker = broker
        self._logger.info("DashboardPlugin registered")

    def create_widget(self) -> QWidget:
        return self._widget_factory(self._broker)
