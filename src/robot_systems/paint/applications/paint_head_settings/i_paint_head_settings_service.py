from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PaintHeadSettings:
    more_paint_sign: int
    preset_spacing: int
    preset_count: int
    min_value: int

    @property
    def max_value(self) -> int:
        return self.min_value + self.preset_spacing * (self.preset_count - 1)


class IPaintHeadSettingsService(ABC):
    @abstractmethod
    def load(self) -> PaintHeadSettings: ...

    @abstractmethod
    def save(self, sign: int, spacing: int, count: int) -> PaintHeadSettings: ...
