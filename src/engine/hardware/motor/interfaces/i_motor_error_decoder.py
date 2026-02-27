from abc import ABC, abstractmethod


class IMotorErrorDecoder(ABC):
    """
    Maps driver-specific integer error codes to human-readable descriptions.
    Implement one per motor controller board/firmware variant.
    Inject into MotorHealthChecker — the health check logic stays generic.
    """

    @abstractmethod
    def decode(self, error_code: int) -> str:
        """Return a description for the given error code. Never raises."""