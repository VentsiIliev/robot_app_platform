from abc import ABC, abstractmethod

from PyQt6.QtWidgets import QWidget

from src.engine.core.message_broker import MessageBroker


class IPlugin(ABC):

    @abstractmethod
    def register(self, broker: MessageBroker) -> None:
        ...

    @abstractmethod
    def create_widget(self) -> QWidget:
        ...