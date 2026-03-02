import logging
from typing import Callable, Dict, List

from src.applications.broker_debug.service.i_broker_debug_service import IBrokerDebugService
from src.engine.core.i_messaging_service import IMessagingService

_logger = logging.getLogger(__name__)


class BrokerDebugApplicationService(IBrokerDebugService):

    def __init__(self, messaging: IMessagingService):
        self._messaging = messaging
        self._spies: Dict[str, Callable] = {}

    def get_all_topics(self) -> List[str]:
        return sorted(self._messaging.get_all_topics())

    def get_subscriber_count(self, topic: str) -> int:
        return self._messaging.get_subscriber_count(topic)

    def publish(self, topic: str, message: str) -> None:
        _logger.debug("Debug publish → %s : %s", topic, message)
        self._messaging.publish(topic, message)

    def subscribe_spy(self, topic: str, callback: Callable) -> None:
        self._messaging.subscribe(topic, callback)
        self._spies[topic] = callback
        _logger.debug("Spy subscribed to %s", topic)

    def unsubscribe_spy(self, topic: str, callback: Callable) -> None:
        self._messaging.unsubscribe(topic, callback)
        self._spies.pop(topic, None)
        _logger.debug("Spy unsubscribed from %s", topic)

    def clear_topic(self, topic: str) -> None:
        self._messaging.clear_topic(topic)

    def get_topic_map(self) -> Dict[str, int]:
        return {t: self._messaging.get_subscriber_count(t)
                for t in self._messaging.get_all_topics()}