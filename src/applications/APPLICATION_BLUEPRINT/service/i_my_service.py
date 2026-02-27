"""
Step 3 — Service interface.

Defines ONLY what this application needs — not the full robot_app or settings_service.
This is the boundary between the application and the rest of the platform.

Rule: if you need data → add a query method.
      if you need an action → add a command method.
      Never pass ISettingsService or IRobotService directly into the application.
"""
from abc import ABC, abstractmethod


class IMyService(ABC):

    # --- Queries ----------------------------------------------------------

    @abstractmethod
    def get_value(self) -> str:
        """Return a value the application needs to display."""
        ...

    # --- Commands ---------------------------------------------------------

    @abstractmethod
    def save_value(self, value: str) -> None:
        """Persist a user change."""
        ...
