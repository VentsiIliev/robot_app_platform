from __future__ import annotations

from src.applications.base.i_application_model import IApplicationModel
from src.applications.shaft_alignment.service.i_shaft_alignment_service import (
    AlignmentSnapshot,
    AlignmentThresholds,
    IShaftAlignmentService,
)
from src.applications.shaft_alignment.settings.shaft_alignment_settings import ShaftAlignmentSettings


class ShaftAlignmentModel(IApplicationModel):
    def __init__(self, service: IShaftAlignmentService) -> None:
        self._service = service
        self._snapshot = AlignmentSnapshot()

    def load(self) -> tuple[AlignmentSnapshot, ShaftAlignmentSettings]:
        self._snapshot = self._service.get_snapshot()
        return self._snapshot, self._service.get_settings()

    def save(self, settings: ShaftAlignmentSettings, **kwargs) -> None:
        self._service.save_settings(settings)

    def get_settings(self) -> ShaftAlignmentSettings:
        return self._service.get_settings()

    def start(self) -> None:
        self._service.start()

    def stop_detection(self) -> None:
        self._service.stop()

    def refresh(self) -> AlignmentSnapshot:
        self._snapshot = self._service.get_snapshot()
        return self._snapshot

    def set_detection_region(self, region: tuple[float, float, float, float]) -> None:
        self._service.set_detection_region(*region)

    def clear_detection_region(self) -> None:
        self._service.clear_detection_region()

    def capture_reference(self, sample_count: int) -> None:
        self._service.capture_reference(sample_count)

    def set_thresholds(self, thresholds: AlignmentThresholds) -> None:
        self._service.set_thresholds(thresholds)

    def close(self) -> None:
        self._service.stop()

    def check_alignment(self) -> bool:
        return self._service.check_alignment()
