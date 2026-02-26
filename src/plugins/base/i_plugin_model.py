from abc import ABC, abstractmethod


class IPluginModel(ABC):
    """
    Base interface for all plugin models.

    Responsible for in-memory state and I/O delegation to the service.
    Has NO knowledge of Qt, views, or controllers.
    """

    @abstractmethod
    def load(self): ...

    @abstractmethod
    def save(self, *args, **kwargs) -> None: ...