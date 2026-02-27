from abc import ABC, abstractmethod


class IHealthCheckable(ABC):
    """
    Optional interface for services that can report their own operational health.
    A service is healthy when it is connected and ready to accept commands.
    Implement this on any service that has a meaningful connected/ready state.
    """

    @abstractmethod
    def is_healthy(self) -> bool: ...