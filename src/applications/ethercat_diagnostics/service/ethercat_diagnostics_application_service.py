from __future__ import annotations

from typing import Any, Callable

from src.applications.ethercat_diagnostics.service.i_ethercat_diagnostics_service import (
    EthercatDiagnosticsSnapshot,
    EthercatSlaveStatus,
    IEthercatDiagnosticsService,
)


class EthercatDiagnosticsApplicationService(IEthercatDiagnosticsService):
    """
    Normalizes EtherCAT diagnostics from a master-like provider.

    The provider is intentionally duck-typed. A future SOEM, IgH, ROS2, or
    vendor adapter can expose any of the generic methods below without changing
    the app layer.
    """

    _STATUS_METHODS = (
        "get_ethercat_diagnostics",
        "get_ethercat_status",
        "get_master_status",
        "get_drive_status",
    )
    _RESET_METHODS = (
        "reset_ethercat_errors",
        "clear_ethercat_errors",
        "reset_drive_errors",
        "reset_errors",
    )

    def __init__(self, provider: object | None = None) -> None:
        self._provider = provider

    def refresh(self) -> EthercatDiagnosticsSnapshot:
        if self._provider is None:
            return EthercatDiagnosticsSnapshot(
                master_state="unavailable",
                master_message="No EtherCAT diagnostics provider is configured",
            )

        status_getter = self._first_callable(self._STATUS_METHODS)
        if status_getter is None:
            return EthercatDiagnosticsSnapshot(
                master_state="unsupported",
                master_message="Configured provider does not expose EtherCAT diagnostics",
            )

        try:
            raw = status_getter() or {}
        except Exception as exc:
            return EthercatDiagnosticsSnapshot(
                master_state="error",
                master_message=str(exc),
                raw={"success": False, "error": str(exc)},
            )

        if isinstance(raw, EthercatDiagnosticsSnapshot):
            return raw
        raw = raw if isinstance(raw, dict) else {"value": raw}
        return self._normalize_snapshot(raw)

    def supports_reset_errors(self) -> bool:
        return self._first_callable(self._RESET_METHODS) is not None

    def reset_errors(self) -> tuple[bool, str]:
        reset = self._first_callable(self._RESET_METHODS)
        if reset is None:
            return False, "Reset is not supported by this EtherCAT diagnostics provider"
        try:
            result = reset()
        except Exception as exc:
            return False, str(exc)
        if isinstance(result, tuple) and len(result) >= 2:
            return bool(result[0]), str(result[1])
        if isinstance(result, dict):
            ok = bool(result.get("success", result.get("ok", False)))
            message = str(result.get("message") or result.get("error") or ("Reset completed" if ok else "Reset failed"))
            return ok, message
        ok = bool(result) if result is not None else True
        return ok, "Reset completed" if ok else "Reset failed"

    def _first_callable(self, names: tuple[str, ...]) -> Callable | None:
        for name in names:
            fn = getattr(self._provider, name, None)
            if callable(fn):
                return fn
        return None

    def _normalize_snapshot(self, raw: dict[str, Any]) -> EthercatDiagnosticsSnapshot:
        slaves = self._normalize_slaves(raw)
        master_state = self._master_state(raw, slaves)
        return EthercatDiagnosticsSnapshot(
            master_state=master_state,
            master_message=self._master_message(raw, master_state),
            slaves=tuple(slaves),
            raw=raw,
        )

    def _normalize_slaves(self, raw: dict[str, Any]) -> list[EthercatSlaveStatus]:
        explicit = raw.get("slaves")
        if isinstance(explicit, list):
            return [self._normalize_slave(item, index + 1) for index, item in enumerate(explicit)]

        status_states = raw.get("status_state")
        statuswords = raw.get("statusword")
        if isinstance(status_states, (list, tuple)) or isinstance(statuswords, (list, tuple)):
            states = list(status_states) if isinstance(status_states, (list, tuple)) else []
            words = list(statuswords) if isinstance(statuswords, (list, tuple)) else []
            count = max(len(states), len(words))
            slaves = []
            for index in range(count):
                state = str(states[index]) if index < len(states) else "unknown"
                statusword = words[index] if index < len(words) else None
                slaves.append(
                    EthercatSlaveStatus(
                        slave_id=index + 1,
                        name=f"Slave {index + 1}",
                        state=state,
                        online=raw.get("success") is not False,
                        operational=self._is_operational(state, raw),
                        error=str(raw.get("error") or "") if raw.get("success") is False else "",
                        statusword=statusword,
                    )
                )
            return slaves

        return ()

    def _normalize_slave(self, raw_slave: object, fallback_id: int) -> EthercatSlaveStatus:
        if not isinstance(raw_slave, dict):
            return EthercatSlaveStatus(slave_id=fallback_id, name=f"Slave {fallback_id}", details={"value": raw_slave})
        state = str(raw_slave.get("state") or raw_slave.get("status") or raw_slave.get("al_state") or "unknown")
        slave_id = raw_slave.get("id", raw_slave.get("slave_id", raw_slave.get("position", fallback_id)))
        online = raw_slave.get("online")
        operational = raw_slave.get("operational")
        return EthercatSlaveStatus(
            slave_id=slave_id,
            name=str(raw_slave.get("name") or raw_slave.get("device") or f"Slave {slave_id}"),
            state=state,
            online=bool(online) if online is not None else None,
            operational=bool(operational) if operational is not None else self._is_operational(state, raw_slave),
            error=str(raw_slave.get("error") or raw_slave.get("fault") or ""),
            statusword=raw_slave.get("statusword"),
            details=dict(raw_slave),
        )

    @staticmethod
    def _is_operational(state: object, raw: dict[str, Any]) -> bool | None:
        text = str(state or "").strip().lower()
        if text in {"op", "operational", "operation_enabled", "operation enabled"}:
            return True
        if text in {"safe_op", "pre_op", "init", "fault", "error", "disabled", "switched_on"}:
            return False
        motion_allowed = raw.get("motion_allowed_by_drive_enable")
        if motion_allowed is not None:
            return bool(motion_allowed)
        return None

    @staticmethod
    def _master_state(raw: dict[str, Any], slaves: list[EthercatSlaveStatus]) -> str:
        if raw.get("success") is False:
            return "error"
        state = str(raw.get("master_state") or raw.get("state") or "").strip()
        if state:
            return state
        if slaves and all(slave.operational is True for slave in slaves):
            return "operational"
        if slaves:
            return "not_ready"
        return "unknown"

    @staticmethod
    def _master_message(raw: dict[str, Any], master_state: str) -> str:
        for key in ("message", "error", "reason"):
            value = str(raw.get(key) or "").strip()
            if value:
                return value
        if master_state == "operational":
            return "All slaves are operational"
        if master_state == "not_ready":
            return "One or more slaves are not operational"
        return "Diagnostics loaded"
