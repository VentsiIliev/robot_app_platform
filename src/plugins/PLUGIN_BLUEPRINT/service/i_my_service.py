"""
Step 3 — Service interface.

Defines ONLY what this plugin needs — not the full robot_app or settings_service.
This is the boundary between the plugin and the rest of the platform.

Rule: if you need data → add a query method.
      if you need an action → add a command method.
      Never pass ISettingsService or IRobotService directly into the plugin.
"""
from abc import ABC, abstractmethod


class IMyService(ABC):

    # --- Queries ----------------------------------------------------------

    @abstractmethod
    def get_value(self) -> str:
        """Return a value the plugin needs to display."""
        ...

    # --- Commands ---------------------------------------------------------

    @abstractmethod
    def save_value(self, value: str) -> None:
        """Persist a user change."""
        ...
