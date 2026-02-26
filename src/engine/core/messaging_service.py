from typing import Any, Callable, List

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.core.message_broker import MessageBroker


class MessagingService(IMessagingService):
    """
    Concrete IMessagingService backed by MessageBroker.

    This is the only class outside engine/core that should be instantiated.
    MessageBroker is an implementation detail — it never leaks beyond this file.
    Swapping the underlying broker in future = replace this class only.
    """

    def __init__(self):
        self._broker = MessageBroker()

    def subscribe(self, topic: str, callback: Callable) -> None:
        self._broker.subscribe(topic, callback)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        self._broker.unsubscribe(topic, callback)

    def publish(self, topic: str, message: Any) -> None:
        self._broker.publish(topic, message)

    def request(self, topic: str, message: Any, timeout: float = 1.0) -> Any:
        return self._broker.request(topic, message, timeout)

    def get_subscriber_count(self, topic: str) -> int:
        return self._broker.get_subscriber_count(topic)

    def get_all_topics(self) -> List[str]:
        return self._broker.get_all_topics()

    def clear_topic(self, topic: str) -> None:
        self._broker.clear_topic(topic)

    def clear_all(self) -> None:
        self._broker.clear_all()
