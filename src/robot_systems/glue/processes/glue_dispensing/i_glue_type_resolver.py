from abc import ABC, abstractmethod


class IGlueTypeResolver(ABC):
    @abstractmethod
    def resolve(self, glue_type: str) -> int:
        """Return motor_address for glue_type, or -1 if not found."""

