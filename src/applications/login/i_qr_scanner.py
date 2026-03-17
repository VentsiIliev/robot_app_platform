from abc import ABC, abstractmethod
from typing import Optional


class IQrScanner(ABC):

    @abstractmethod
    def scan(self) -> Optional[str]:
        """Capture the latest camera frame and return a decoded QR payload,
        or None if no QR code is detected."""
