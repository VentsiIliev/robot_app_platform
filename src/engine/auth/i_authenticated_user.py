from abc import ABC, abstractmethod
from enum import Enum


class IAuthenticatedUser(ABC):

    @property
    @abstractmethod
    def user_id(self) -> str:
        """Stable identifier for this user."""

    @property
    @abstractmethod
    def role(self) -> Enum:
        """The user's role. Compared via .value — no concrete Role type assumed."""
