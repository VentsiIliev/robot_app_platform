from abc import ABC, abstractmethod


class IPluginController(ABC):
    """
    Base interface for all plugin controllers.

    The only layer allowed touching both model and view.
    Enforces the lifecycle contract:
      - load(): called once by the factory — populates view from model
      - stop(): called on view destruction — unsubscribes broker topics,
                 stops threads
    """

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...