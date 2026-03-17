from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple


class ILocalizationService(ABC):

    @abstractmethod
    def set_language(self, code: str) -> None: ...

    @abstractmethod
    def get_language(self) -> str: ...

    @abstractmethod
    def available_languages(self) -> List[Tuple[str, str]]: ...

    @abstractmethod
    def translate(self, context: str, source_text: str, fallback: str | None = None) -> str: ...

    @abstractmethod
    def sync_selector(self, selector) -> None: ...
