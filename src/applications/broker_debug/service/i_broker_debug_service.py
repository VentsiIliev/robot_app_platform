from abc import ABC, abstractmethod
from typing import Callable, Dict, List


class IBrokerDebugService(ABC):

    @abstractmethod
    def get_all_topics(self) -> List[str]: ...

    @abstractmethod
    def get_subscriber_count(self, topic: str) -> int: ...

    @abstractmethod
    def publish(self, topic: str, message: str) -> None: ...

    @abstractmethod
    def subscribe_spy(self, topic: str, callback: Callable) -> None: ...

    @abstractmethod
    def unsubscribe_spy(self, topic: str, callback: Callable) -> None: ...

    @abstractmethod
    def clear_topic(self, topic: str) -> None: ...

    @abstractmethod
    def get_topic_map(self) -> Dict[str, int]: ...