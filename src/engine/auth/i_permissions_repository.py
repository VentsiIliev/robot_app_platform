from abc import ABC, abstractmethod


class IPermissionsRepository(ABC):

    @abstractmethod
    def get_allowed_role_values(self, app_id: str) -> list[str]:
        """Return role value strings for this app_id.
        Defaults to ['Admin'] if the app_id is not present."""

    @abstractmethod
    def set_allowed_role_values(self, app_id: str, role_values: list[str]) -> None:
        """Persist the given role values for app_id immediately.
        Must store a copy — mutations to the input list must not affect stored data."""

    @abstractmethod
    def get_all(self) -> dict[str, list[str]]:
        """Return a full copy of the permissions map keyed by app_id."""
