from abc import ABC, abstractmethod


class ISoftwareUpdateService(ABC):
    @abstractmethod
    def get_status(self) -> dict:
        """Return installed/staged versions and configuration location."""

    @abstractmethod
    def check(self) -> dict:
        """Return the authenticated latest release and availability."""

    @abstractmethod
    def download(self) -> dict:
        """Download and stage the latest verified platform release."""

    @abstractmethod
    def schedule_installation(self) -> None:
        """Queue activation after the managed application has closed."""
