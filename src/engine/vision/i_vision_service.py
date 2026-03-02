from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class IVisionService(ABC):

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def set_raw_mode(self, enabled: bool) -> None: ...

    @abstractmethod
    def capture_calibration_image(self) -> tuple[bool, str]: ...

    @abstractmethod
    def calibrate_camera(self) -> tuple[bool, str]: ...

    @abstractmethod
    def update_settings(self, settings: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def save_work_area(self, area_type: str, pixel_points: List[Tuple[int, int]]) -> tuple[bool, str]: ...

    @abstractmethod
    def get_work_area(self, area_type: str) -> tuple[bool, str, Optional[List]]: ...
