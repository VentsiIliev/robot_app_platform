from __future__ import annotations

from functools import partial

from src.applications.base.background_worker import BackgroundWorker

from .paint_head_settings_model import PaintHeadSettingsModel
from .paint_head_settings_view import PaintHeadSettingsView


class PaintHeadSettingsController(BackgroundWorker):
    def __init__(self, model: PaintHeadSettingsModel, view: PaintHeadSettingsView) -> None:
        super().__init__()
        self._model = model
        self._view = view
        self._active = False
        self._view.save_requested.connect(self._on_save)

    def load(self) -> None:
        self._active = True
        try:
            settings = self._model.load()
        except (KeyError, ValueError) as error:
            self._view.set_error(str(error))
            return
        self._view.set_settings(
            settings.more_paint_sign,
            settings.preset_spacing,
            settings.preset_count,
            settings.min_value,
        )

    def stop(self) -> None:
        self._active = False
        self._stop_threads()

    def _on_save(self, sign: int, spacing: int, count: int) -> None:
        if not self._active:
            return
        self._view.set_busy(True)
        self._run_in_thread(
            fn=partial(self._model.save, sign, spacing, count),
            on_done=self._on_saved,
            on_error=self._on_error,
        )

    def _on_saved(self, settings) -> None:
        if self._active:
            self._view.set_busy(False)
            self._view.set_saved(
                settings.more_paint_sign,
                settings.preset_spacing,
                settings.preset_count,
                settings.min_value,
            )

    def _on_error(self, message: str) -> None:
        if self._active:
            self._view.set_busy(False)
            self._view.set_error(message)
