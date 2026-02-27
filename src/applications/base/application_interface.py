from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QWidget
from src.engine.core.i_messaging_service import IMessagingService


class IApplication(ABC):

    @abstractmethod
    def register(self, messaging_service: IMessagingService) -> None: ...

    @abstractmethod
    def create_widget(self) -> QWidget: ...
