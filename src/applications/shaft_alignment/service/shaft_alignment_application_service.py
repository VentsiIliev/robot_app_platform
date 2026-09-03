from __future__ import annotations

from src.applications.shaft_alignment.service.i_shaft_alignment_service import (
    AlignmentSnapshot,
    AlignmentThresholds,
    IShaftAlignmentService,
)
from src.applications.shaft_alignment.settings.shaft_alignment_settings import ShaftAlignmentSettings


class ShaftAlignmentApplicationService(IShaftAlignmentService):
    """Adapt an injected alignment backend without coupling the app to a robot system."""

    def __init__(self, backend: IShaftAlignmentService) -> None:
        self._backend = backend

    def start(self) -> None:
        self._backend.start()

    def stop(self) -> None:
        self._backend.stop()

    def get_snapshot(self) -> AlignmentSnapshot:
        return self._backend.get_snapshot()

    def set_detection_region(self, left, top, right, bottom) -> None:
        self._backend.set_detection_region(left, top, right, bottom)

    def clear_detection_region(self) -> None:
        self._backend.clear_detection_region()

    def capture_reference(self, sample_count: int) -> None:
        self._backend.capture_reference(sample_count)

    def set_thresholds(self, thresholds: AlignmentThresholds) -> None:
        self._backend.set_thresholds(thresholds)

    def get_settings(self) -> ShaftAlignmentSettings:
        return self._backend.get_settings()

    def save_settings(self, settings: ShaftAlignmentSettings) -> None:
        self._backend.save_settings(settings)

    def check_alignment(self) -> bool:
        return self._backend.check_alignment()
