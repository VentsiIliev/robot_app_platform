from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer

from src.applications.base.i_application_controller import IApplicationController
from src.applications.shaft_alignment.model.shaft_alignment_model import ShaftAlignmentModel
from src.applications.shaft_alignment.service.i_shaft_alignment_service import AlignmentThresholds
from src.applications.shaft_alignment.view.shaft_alignment_view import ShaftAlignmentView


class ShaftAlignmentController(IApplicationController):
    def __init__(self, model: ShaftAlignmentModel, view: ShaftAlignmentView) -> None:
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)
        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._on_refresh)
        self._stopped = False

        self._view.capture_reference_requested.connect(self._on_capture_reference)
        self._view.region_selected.connect(self._on_region_selected)
        self._view.clear_region_requested.connect(self._on_clear_region)
        self._view.thresholds_changed.connect(self._on_thresholds_changed)
        self._view.save_settings_requested.connect(self._on_save_settings)
        self._view.check_alignment_requested.connect(self._on_check_alignment)

    def load(self) -> None:
        snapshot, settings = self._model.load()
        self._view.set_settings(settings)
        self._view.set_snapshot(snapshot)
        self._on_thresholds_changed(*self._view.threshold_values())
        self._model.start()
        self._timer.start()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._timer.stop()
        self._model.close()

    def _on_refresh(self) -> None:
        try:
            self._view.set_snapshot(self._model.refresh())
            self._view.set_persisted_settings(self._model.get_settings())
        except Exception as exc:
            self._logger.exception("Shaft alignment refresh failed")
            self._view.set_error(str(exc))

    def _on_capture_reference(self, sample_count: int) -> None:
        self._model.capture_reference(sample_count)

    def _on_region_selected(self, left, top, right, bottom) -> None:
        self._model.set_detection_region((left, top, right, bottom))

    def _on_clear_region(self) -> None:
        self._model.clear_detection_region()

    def _on_thresholds_changed(self, dx, dy, drz, dw, dh) -> None:
        self._model.set_thresholds(AlignmentThresholds(dx, dy, drz, dw, dh))

    def _on_save_settings(self, settings) -> None:
        try:
            self._model.save(settings)
            self._view.set_settings(settings)
            self._view.show_settings_saved()
        except Exception as exc:
            self._logger.exception("Failed to save shaft alignment settings")
            self._view.set_settings_error(str(exc))

    def _on_check_alignment(self) -> None:
        try:
            self._view.show_alignment_check(self._model.check_alignment())
        except Exception as exc:
            self._logger.exception("Shaft alignment check failed")
            self._view.set_error(str(exc))
