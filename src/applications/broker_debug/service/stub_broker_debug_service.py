import logging
from typing import Callable, Dict, List

from src.applications.broker_debug.service.i_broker_debug_service import IBrokerDebugService

_logger = logging.getLogger(__name__)

_STUB_TOPICS = {
    "vision-vision_service/latest-image":        3,
    "vision-vision_service/threshold-image":     1,
    "vision-service/state":              2,
    "process/glue/state":                4,
    "weight-cell/reading":               2,
    "robot/state":                       1,
}


class StubBrokerDebugService(IBrokerDebugService):

    def __init__(self):
        self._topics = dict(_STUB_TOPICS)

    def get_all_topics(self) -> List[str]:
        return sorted(self._topics.keys())

    def get_subscriber_count(self, topic: str) -> int:
        return self._topics.get(topic, 0)

    def publish(self, topic: str, message: str) -> None:
        _logger.info("Stub publish → %s : %s", topic, message)

    def subscribe_spy(self, topic: str, callback: Callable) -> None:
        _logger.info("Stub spy subscribe → %s", topic)

    def unsubscribe_spy(self, topic: str, callback: Callable) -> None:
        _logger.info("Stub spy unsubscribe → %s", topic)

    def clear_topic(self, topic: str) -> None:
        self._topics.pop(topic, None)
        _logger.info("Stub clear topic → %s", topic)

    def get_topic_map(self) -> Dict[str, int]:
        return dict(self._topics)