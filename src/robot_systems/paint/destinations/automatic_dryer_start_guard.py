from __future__ import annotations

from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    DashboardCommandResult,
)


class AutomaticDryerStartGuard:
    """Autodryer-specific production-start policy kept outside the dashboard."""

    def __init__(self, dryer, persist_enabled=None, *, development_mode=False) -> None:
        self._dryer = dryer
        self._persist_enabled = persist_enabled
        self._development_mode = bool(development_mode)

    def state(self, mode: str) -> dict[str, object]:
        if str(mode).strip().lower() not in {"auto", "demo"}:
            return {"required": False, "ready": True}
        if self._dryer is None:
            return self._state(False, False, "Automatic dryer service is not available.")
        try:
            enabled = bool(self._dryer.is_enabled())
            healthy = bool(self._dryer.is_healthy())
            message = str(getattr(self._dryer, "last_error", None) or "")
        except Exception as exc:
            return self._state(True, False, f"Could not read automatic dryer state: {exc}")
        return self._state(True, enabled and healthy, message, enabled=enabled)

    def prepare(self, mode: str) -> DashboardCommandResult:
        if self._dryer is None:
            return DashboardCommandResult(False, "Automatic dryer service is not available.")
        try:
            if not bool(self._dryer.is_healthy()) and not bool(self._dryer.enable()):
                if callable(self._persist_enabled):
                    self._persist_enabled(False)
                return DashboardCommandResult(
                    False,
                    str(getattr(self._dryer, "last_error", None) or "Dryer initialization failed."),
                )
            if callable(self._persist_enabled):
                self._persist_enabled(True)
        except Exception as exc:
            return DashboardCommandResult(False, f"Could not enable automatic dryer: {exc}")
        return DashboardCommandResult(True, f"Production destination prepared for {mode} mode.")

    def _state(self, available, ready, message, *, enabled=False):
        return {
            "required": True,
            "available": bool(available),
            "ready": bool(ready),
            "enabled": bool(enabled),
            "message": str(message),
            "title": "Automatic Dryer",
            "prepare_prompt": "Automatic drying requires the dryer. Do you want to enable it now?",
            "bypass_allowed": self._development_mode,
            "bypass_prompt": "The dryer is disabled. Continue without automatic dryer commands?",
        }
