from abc import ABC, abstractmethod


class IExposureControl(ABC):
    @abstractmethod
    def set_auto_exposure(self, enabled: bool) -> None: ...