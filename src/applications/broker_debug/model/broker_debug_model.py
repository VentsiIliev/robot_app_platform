from typing import Callable, Dict, List

from src.applications.base.i_application_model import IApplicationModel
from src.applications.broker_debug.service.i_broker_debug_service import IBrokerDebugService


class BrokerDebugModel(IApplicationModel):

    def __init__(self, service: IBrokerDebugService):
        self._service = service

    def load(self) -> Dict[str, int]:
        return self._service.get_topic_map()

    def save(self, *args, **kwargs) -> None:
        pass

    def refresh(self) -> Dict[str, int]:
        return self._service.get_topic_map()

    def publish(self, topic: str, message: str) -> None:
        self._service.publish(topic, message)

    def subscribe_spy(self, topic: str, callback: Callable) -> None:
        self._service.subscribe_spy(topic, callback)

    def unsubscribe_spy(self, topic: str, callback: Callable) -> None:
        self._service.unsubscribe_spy(topic, callback)

    def clear_topic(self, topic: str) -> None:
        self._service.clear_topic(topic)