from abc import ABC, abstractmethod
from typing import Any, Callable, List


class IMessagingService(ABC):

    @abstractmethod
    def subscribe(self, topic: str, callback: Callable) -> None: ...

    @abstractmethod
    def unsubscribe(self, topic: str, callback: Callable) -> None: ...

    @abstractmethod
    def publish(self, topic: str, message: Any) -> None: ...

    @abstractmethod
    def request(self, topic: str, message: Any, timeout: float = 1.0) -> Any: ...

    @abstractmethod
    def get_subscriber_count(self, topic: str) -> int: ...

    @abstractmethod
    def get_all_topics(self) -> List[str]: ...

    @abstractmethod
    def clear_topic(self, topic: str) -> None: ...

    @abstractmethod
    def clear_all(self) -> None: ...
