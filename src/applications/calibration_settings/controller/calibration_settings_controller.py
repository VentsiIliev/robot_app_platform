from src.applications.base.i_application_controller import IApplicationController
from src.applications.calibration_settings.mapper import CalibrationSettingsMapper
from src.applications.calibration_settings.model.calibration_settings_model import (
    CalibrationSettingsModel,
)
from src.applications.calibration_settings.view.calibration_settings_view import (
    CalibrationSettingsView,
)


class CalibrationSettingsController(IApplicationController):

    def __init__(self, model: CalibrationSettingsModel, view: CalibrationSettingsView, _messaging=None):
        self._model = model
        self._view = view

    def load(self) -> None:
        settings = self._model.load()
        self._view.settings_view.set_values(CalibrationSettingsMapper.to_flat_dict(settings))
        self._view.save_requested.connect(self._on_save)
        self._view.workobject_capture_requested.connect(self._on_workobject_capture)
        self._view.workobject_solve_requested.connect(self._on_workobject_solve)
        self._view.workobject_save_requested.connect(self._on_workobject_save)

    def stop(self) -> None:
        try:
            self._view.save_requested.disconnect(self._on_save)
        except Exception:
            pass
        for signal, handler in (
            (self._view.workobject_capture_requested, self._on_workobject_capture),
            (self._view.workobject_solve_requested, self._on_workobject_solve),
            (self._view.workobject_save_requested, self._on_workobject_save),
        ):
            try:
                signal.disconnect(handler)
            except Exception:
                pass

    def _on_save(self, flat: dict) -> None:
        updated = CalibrationSettingsMapper.from_flat_dict(flat, self._model.current_settings)
        self._model.save(updated)

    def _on_workobject_capture(self, point: str) -> None:
        ok, msg, payload = self._model.capture_workobject_point(point)
        if ok:
            self._view.set_workobject_capture(payload.get("point", point), payload.get("pose"))
        self._view.set_workobject_result(ok, msg, payload)

    def _on_workobject_solve(self, user_id: int, name: str) -> None:
        ok, msg, payload = self._model.solve_workobject(user_id, name)
        self._view.set_workobject_result(ok, msg, payload)

    def _on_workobject_save(self, user_id: int, name: str) -> None:
        ok, msg, payload = self._model.save_workobject(user_id, name=name, persist=True)
        self._view.set_workobject_result(ok, msg, payload)
